import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from qdrant_client.models import PointStruct
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from rag.chunker import chunk_pdf, chunk_text
from rag.document_model import Document, DocType
from rag.embedder import embed
from rag.store import upsert, search

router = APIRouter(prefix="/rag")


async def _resolve_doc_id(db: AsyncSession, source: str) -> str:
    existing = await db.execute(select(Document.id).where(Document.source == source))
    found = existing.scalar_one_or_none()
    return found or str(uuid.uuid4())


# ── upload PDF ────────────────────────────────────────────────────
@router.post("/upload")
async def upload(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    content = await file.read()
    chunks = chunk_pdf(content, file.filename)
    if not chunks:
        raise HTTPException(status_code=422, detail="No text could be extracted from the PDF.")

    doc_id = await _resolve_doc_id(db, file.filename)
    points = [
        PointStruct(id=str(uuid.uuid4()), vector=embed(c["text"]), payload={**c, "doc_id": doc_id})
        for c in chunks
    ]
    upsert(points)

    stmt = (
        insert(Document)
        .values(
            id=doc_id,
            source=file.filename,
            filename=file.filename,
            type=DocType.pdf,
            chunk_count=len(points),
            file_size=len(content),
            uploaded_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["source"],
            set_={"chunk_count": len(points), "file_size": len(content), "uploaded_at": datetime.now(timezone.utc)},
        )
    )
    await db.execute(stmt)
    await db.commit()

    return {"id": doc_id, "file": file.filename, "chunks": len(points)}


# ── add plain text ────────────────────────────────────────────────
class TextPayload(BaseModel):
    text: str
    source: str = "manual entry"


@router.post("/add-text")
async def add_text(body: TextPayload, db: AsyncSession = Depends(get_db)):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    chunks = chunk_text(body.text.strip(), body.source)
    doc_id = await _resolve_doc_id(db, body.source)
    points = [
        PointStruct(id=str(uuid.uuid4()), vector=embed(c["text"]), payload={**c, "doc_id": doc_id})
        for c in chunks
    ]
    upsert(points)

    stmt = (
        insert(Document)
        .values(
            id=doc_id,
            source=body.source,
            filename=body.source,
            type=DocType.text,
            chunk_count=len(points),
            file_size=None,
            uploaded_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["source"],
            set_={"chunk_count": len(points), "uploaded_at": datetime.now(timezone.utc)},
        )
    )
    await db.execute(stmt)
    await db.commit()

    return {"id": doc_id, "source": body.source, "chunks": len(points)}


# ── list indexed sources ──────────────────────────────────────────
@router.get("/documents")
async def documents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).order_by(Document.uploaded_at.desc()))
    docs = result.scalars().all()
    return [
        {
            "id": d.id,
            "file": d.source,
            "filename": d.filename,
            "type": d.type,
            "chunks": d.chunk_count,
            "file_size": d.file_size,
            "uploaded_at": d.uploaded_at.isoformat(),
        }
        for d in docs
    ]


# ── chat with a specific source ───────────────────────────────────
class KbMessage(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    messages: list[KbMessage]   # full history, last item is the new user question
    id: str
    model: str | None = None


def _get_provider(model_override: str | None = None):
    from providers.ollama import OllamaProvider
    from providers.gemini import GeminiProvider
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    model = model_override or os.getenv("LLM_MODEL", "gemma3").strip()
    if provider == "gemini":
        return GeminiProvider(os.getenv("GEMINI_API_KEY", ""), model)
    return OllamaProvider(os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), model)


@router.post("/query")
def query_kb(req: QueryRequest):
    last_user = next((m.content for m in reversed(req.messages) if m.role == "user"), None)
    if not last_user:
        raise HTTPException(status_code=400, detail="No user message found.")

    hits = search(embed(last_user), id_filters=[req.id], score_threshold=0.4)

    if not hits:
        def no_context():
            yield "data: I couldn't find relevant information in this document for that question.\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(no_context(), media_type="text/event-stream")

    context = "\n---\n".join(f"[p.{h['page']}] {h['text']}" for h in hits)
    source_label = hits[0].get("source", req.id)
    system = (
        f"You are a helpful assistant. Answer the user's question using only the context below "
        f"from the document '{source_label}'. "
        "If the answer is not in the context, say so clearly. Be concise.\n\n"
        f"Context:\n{context}"
    )

    messages = [{"role": "system", "content": system}] + [m.model_dump() for m in req.messages]
    provider = _get_provider(req.model)

    def event_stream():
        sources = [{"source": h["source"], "page": h["page"], "score": h.get("score")} for h in hits]
        yield f"event: sources\ndata: {json.dumps(sources)}\n\n"
        for token in provider.stream(messages):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
