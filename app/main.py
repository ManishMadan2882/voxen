import json
import logging
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=False))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from db import engine, Base, get_db  # noqa: E402
import users.user_model  # noqa: F401, E402 — registers ORM model with Base
import rag.document_model  # noqa: F401, E402 — registers ORM model with Base
import prompts.prompt_model  # noqa: F401, E402 — registers ORM model with Base
import agents.agent_model  # noqa: F401, E402 — registers ORM model with Base
from models import StreamRequest  # noqa: E402
from prompts.prompt_model import Prompt  # noqa: E402
from prompts.router import router as prompts_router  # noqa: E402
from agents.router import router as agents_router  # noqa: E402
from providers.ollama import OllamaProvider  # noqa: E402
from providers.gemini import GeminiProvider  # noqa: E402
from rag.router import router as rag_router  # noqa: E402
from rag.embedder import embed  # noqa: E402
from rag.store import search  # noqa: E402
from users.auth import get_current_user  # noqa: E402
from users.user_model import User  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(rag_router)
app.include_router(prompts_router)
app.include_router(agents_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_provider(model_override: str | None = None):
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    model = model_override or os.getenv("LLM_MODEL", "gemma3").strip()
    if provider == "gemini":
        return GeminiProvider(os.getenv("GEMINI_API_KEY", ""), model)
    return OllamaProvider(os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), model)


@app.get("/health")
def health():
    return {"ok": True}


SYSTEM_PROMPT = (
    "You are a friendly customer support voice assistant. "
    "Keep responses short and clear — suitable for spoken conversation. "
    "Avoid bullet points, markdown, or long paragraphs. "
    "If you cannot help, offer to connect the caller to a human agent."
)


@app.post("/stream")
async def stream(
    req: StreamRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    provider = _get_provider(req.model)

    system_prompt = SYSTEM_PROMPT
    if req.prompt_id:
        result = await db.execute(
            select(Prompt.content).where(Prompt.id == req.prompt_id, Prompt.user_id == current_user.id)
        )
        custom = result.scalar_one_or_none()
        if custom:
            system_prompt = custom

    # RAG: build query from last 3 user turns for better context recall
    recent = [m.content for m in req.messages if m.role == "user"][-3:]
    hits: list[dict] = []
    rag_context = ""
    if recent:
        try:
            hits = search(
                embed(" ".join(recent)),
                id_filters=req.ids or None,
                score_threshold=0.4 if req.ids else 0.55,
            )
            if hits:
                rag_context = "\n\nRelevant knowledge base context:\n" + "\n---\n".join(
                    f"[{h['source']} p.{h['page']}] {h['text']}" for h in hits
                )
        except Exception:
            logging.exception("RAG retrieval failed (ids=%s)", req.ids)

    messages = [{"role": "system", "content": system_prompt + rag_context}] + [m.model_dump() for m in req.messages]

    def event_stream():
        if hits:
            sources = [{"source": h["source"], "page": h["page"], "score": h.get("score")} for h in hits]
            yield f"event: sources\ndata: {json.dumps(sources)}\n\n"
        for token in provider.stream(messages):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
