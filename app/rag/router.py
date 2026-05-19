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

import httpx

from db import get_db
from rag.chunker import chunk_text
from rag.document_model import Document, DocType
from rag.embedder import embed
from rag.ingestors import SUPPORTED_EXTENSIONS, HttpWebIngestor, get_file_ingestor
from rag.store import upsert, search
from users.auth import get_current_user
from users.user_model import User


router = APIRouter(prefix="/rag")


async def _resolve_doc_id(db: AsyncSession, user_id: str, source: str) -> str:
    existing = await db.execute(
        select(Document.id).where(Document.user_id == user_id, Document.source == source)
    )
    found = existing.scalar_one_or_none()
    return found or str(uuid.uuid4())


# ── upload file (pdf, docx, xlsx, csv, md, txt) ───────────────────
@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext or 'unknown'}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )
    content = await file.read()
    try:
        ingestor = get_file_ingestor(ext)
        chunks = ingestor.ingest(content, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {e}")
    if not chunks:
        raise HTTPException(status_code=422, detail="No text could be extracted from the file.")

    doc_type = ingestor.doc_type
    doc_id = await _resolve_doc_id(db, current_user.id, filename)
    points = [
        PointStruct(id=str(uuid.uuid4()), vector=embed(c["text"]), payload={**c, "doc_id": doc_id})
        for c in chunks
    ]
    upsert(points)

    stmt = (
        insert(Document)
        .values(
            id=doc_id,
            user_id=current_user.id,
            source=filename,
            filename=filename,
            type=doc_type,
            chunk_count=len(points),
            file_size=len(content),
            uploaded_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["user_id", "source"],
            set_={"chunk_count": len(points), "file_size": len(content), "uploaded_at": datetime.now(timezone.utc)},
        )
    )
    await db.execute(stmt)
    await db.commit()

    return {"id": doc_id, "file": filename, "chunks": len(points)}


# ── ingest a web URL ──────────────────────────────────────────────
class UrlPayload(BaseModel):
    url: str


@router.post("/add-url")
async def add_url(
    body: UrlPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty.")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    try:
        chunks, title = HttpWebIngestor().ingest(url)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {e}")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to scrape URL: {e}")
    if not chunks:
        raise HTTPException(status_code=422, detail="No text could be extracted from the URL.")

    doc_id = await _resolve_doc_id(db, current_user.id, url)
    points = [
        PointStruct(id=str(uuid.uuid4()), vector=embed(c["text"]), payload={**c, "doc_id": doc_id})
        for c in chunks
    ]
    upsert(points)

    stmt = (
        insert(Document)
        .values(
            id=doc_id,
            user_id=current_user.id,
            source=url,
            filename=title or url,
            type=DocType.url,
            chunk_count=len(points),
            file_size=None,
            uploaded_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["user_id", "source"],
            set_={"chunk_count": len(points), "uploaded_at": datetime.now(timezone.utc)},
        )
    )
    await db.execute(stmt)
    await db.commit()

    return {"id": doc_id, "source": url, "title": title, "chunks": len(points)}


# ── add plain text ────────────────────────────────────────────────
class TextPayload(BaseModel):
    text: str
    source: str = "manual entry"


@router.post("/add-text")
async def add_text(
    body: TextPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    chunks = chunk_text(body.text.strip(), body.source)
    doc_id = await _resolve_doc_id(db, current_user.id, body.source)
    points = [
        PointStruct(id=str(uuid.uuid4()), vector=embed(c["text"]), payload={**c, "doc_id": doc_id})
        for c in chunks
    ]
    upsert(points)

    stmt = (
        insert(Document)
        .values(
            id=doc_id,
            user_id=current_user.id,
            source=body.source,
            filename=body.source,
            type=DocType.text,
            chunk_count=len(points),
            file_size=None,
            uploaded_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["user_id", "source"],
            set_={"chunk_count": len(points), "uploaded_at": datetime.now(timezone.utc)},
        )
    )
    await db.execute(stmt)
    await db.commit()

    return {"id": doc_id, "source": body.source, "chunks": len(points)}


# ── list indexed sources ──────────────────────────────────────────
@router.get("/documents")
async def documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.uploaded_at.desc())
    )
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
async def query_kb(
    req: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    last_user = next((m.content for m in reversed(req.messages) if m.role == "user"), None)
    if not last_user:
        raise HTTPException(status_code=400, detail="No user message found.")

    owns = await db.execute(
        select(Document.id).where(Document.id == req.id, Document.user_id == current_user.id)
    )
    if owns.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found.")

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
