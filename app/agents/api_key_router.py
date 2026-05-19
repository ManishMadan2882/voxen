import hashlib
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agents.agent_model import Agent
from agents.api_key_model import AgentApiKey
from db import get_db
from prompts.prompt_model import Prompt
from providers.gemini import GeminiProvider
from providers.ollama import OllamaProvider
from rag.embedder import embed
from rag.store import search
from users.auth import get_current_user
from users.user_model import User

_bearer = HTTPBearer(auto_error=False)

# ── helpers ──────────────────────────────────────────────────────────────────

KEY_PREFIX = "vxn_"
DISPLAY_LEN = 16  # chars of raw key kept for UI display


def _generate_raw_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _serialize_key(k: AgentApiKey) -> dict:
    return {
        "id": k.id,
        "agent_id": k.agent_id,
        "name": k.name,
        "key_prefix": k.key_prefix,
        "is_active": k.is_active,
        "created_at": k.created_at.isoformat(),
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
    }


def _get_provider(model_override: str | None = None):
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    model = model_override or os.getenv("LLM_MODEL", "gemma3").strip()
    if provider == "gemini":
        return GeminiProvider(os.getenv("GEMINI_API_KEY", ""), model)
    return OllamaProvider(os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), model)


# ── auth dependency for public key-based access ───────────────────────────────

async def _get_agent_from_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    db: AsyncSession = Depends(get_db),
) -> tuple[AgentApiKey, Agent]:
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing API key.")

    raw = credentials.credentials
    if not raw.startswith(KEY_PREFIX):
        raise HTTPException(status_code=401, detail="Invalid API key format.")

    key_hash = _hash_key(raw)
    result = await db.execute(
        select(AgentApiKey).where(AgentApiKey.key_hash == key_hash, AgentApiKey.is_active.is_(True))
    )
    api_key_row = result.scalar_one_or_none()
    if api_key_row is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key.")

    agent_result = await db.execute(select(Agent).where(Agent.id == api_key_row.agent_id))
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")

    # Update last_used_at without blocking the stream
    await db.execute(
        update(AgentApiKey)
        .where(AgentApiKey.id == api_key_row.id)
        .values(last_used_at=datetime.now(timezone.utc))
    )
    await db.commit()

    return api_key_row, agent


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ApiKeyPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class PublicStreamMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class PublicStreamRequest(BaseModel):
    messages: list[PublicStreamMessage]
    model: str | None = None


# ── Authenticated management routes ──────────────────────────────────────────

management_router = APIRouter(prefix="/agents")


@management_router.get("/{agent_id}/keys")
async def list_api_keys(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Confirm the agent belongs to the requesting user
    agent_check = await db.execute(
        select(Agent.id).where(Agent.id == agent_id, Agent.user_id == current_user.id)
    )
    if agent_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Agent not found.")

    result = await db.execute(
        select(AgentApiKey)
        .where(AgentApiKey.agent_id == agent_id)
        .order_by(AgentApiKey.created_at.desc())
    )
    return [_serialize_key(k) for k in result.scalars().all()]


@management_router.post("/{agent_id}/keys", status_code=201)
async def create_api_key(
    agent_id: str,
    body: ApiKeyPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent_check = await db.execute(
        select(Agent.id).where(Agent.id == agent_id, Agent.user_id == current_user.id)
    )
    if agent_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Agent not found.")

    raw_key = _generate_raw_key()
    key_row = AgentApiKey(
        agent_id=agent_id,
        user_id=current_user.id,
        name=body.name.strip(),
        key_prefix=raw_key[:DISPLAY_LEN],
        key_hash=_hash_key(raw_key),
    )
    db.add(key_row)
    await db.commit()
    await db.refresh(key_row)

    # Raw key is returned only this once; it cannot be retrieved again
    return {**_serialize_key(key_row), "key": raw_key}


@management_router.delete("/{agent_id}/keys/{key_id}")
async def revoke_api_key(
    agent_id: str,
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        delete(AgentApiKey).where(
            AgentApiKey.id == key_id,
            AgentApiKey.agent_id == agent_id,
            AgentApiKey.user_id == current_user.id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="API key not found.")
    await db.commit()
    return {"id": key_id, "deleted": True}


# ── Public streaming route ────────────────────────────────────────────────────

public_router = APIRouter(prefix="/v1")


@public_router.post("/stream")
async def public_stream(
    req: PublicStreamRequest,
    db: AsyncSession = Depends(get_db),
    auth: tuple[AgentApiKey, Agent] = Depends(_get_agent_from_api_key),
):
    """Streaming endpoint for client applications.  Only requires a publishable
    API key; the agent's internal configuration (prompt, knowledge base) is
    never exposed to the caller."""
    _, agent = auth

    prompt_result = await db.execute(select(Prompt.content).where(Prompt.id == agent.prompt_id))
    system_prompt = prompt_result.scalar_one_or_none()
    if not system_prompt:
        raise HTTPException(status_code=500, detail="Agent configuration error.")

    recent = [m.content for m in req.messages if m.role == "user"][-3:]
    hits: list[dict] = []
    rag_context = ""
    if recent:
        try:
            hits = search(
                embed(" ".join(recent)),
                id_filters=[agent.knowledge_base_id],
                score_threshold=0.4,
            )
            if hits:
                rag_context = "\n\nRelevant knowledge base context:\n" + "\n---\n".join(
                    f"[{h['source']} p.{h['page']}] {h['text']}" for h in hits
                )
        except Exception:
            logging.exception("RAG retrieval failed (agent=%s)", agent.id)

    messages = [{"role": "system", "content": system_prompt + rag_context}] + [
        m.model_dump() for m in req.messages
    ]
    provider = _get_provider(req.model)

    def event_stream():
        if hits:
            sources = [{"source": h["source"], "page": h["page"], "score": h.get("score")} for h in hits]
            yield f"event: sources\ndata: {json.dumps(sources)}\n\n"
        for token in provider.stream(messages):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
