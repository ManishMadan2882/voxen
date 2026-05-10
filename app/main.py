import json
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from models import StreamRequest
from providers.ollama import OllamaProvider
from providers.gemini import GeminiProvider
from rag.router import router as rag_router
from rag.embedder import embed
from rag.store import search

load_dotenv()

app = FastAPI()

app.include_router(rag_router)

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
def stream(req: StreamRequest):
    provider = _get_provider(req.model)

    # RAG: build query from last 3 user turns for better context recall
    recent = [m.content for m in req.messages if m.role == "user"][-3:]
    hits: list[dict] = []
    rag_context = ""
    if recent:
        try:
            hits = search(embed(" ".join(recent)), source_filters=req.sources or None)
            if hits:
                rag_context = "\n\nRelevant knowledge base context:\n" + "\n---\n".join(
                    f"[{h['source']} p.{h['page']}] {h['text']}" for h in hits
                )
        except Exception:
            pass

    messages = [{"role": "system", "content": SYSTEM_PROMPT + rag_context}] + [m.model_dump() for m in req.messages]

    def event_stream():
        if hits:
            sources = [{"source": h["source"], "page": h["page"], "score": h.get("score")} for h in hits]
            yield f"event: sources\ndata: {json.dumps(sources)}\n\n"
        for token in provider.stream(messages):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
