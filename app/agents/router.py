import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from agents.agent_model import Agent
from prompts.prompt_model import Prompt
from providers import get_provider
from rag.embedder import embed
from rag.store import search
from users.auth import get_current_user
from users.user_model import User

router = APIRouter(prefix="/agents")


class AgentPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    prompt_id: str = Field(min_length=1)
    knowledge_base_id: str = Field(min_length=1)


class AgentMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class AgentStreamRequest(BaseModel):
    messages: list[AgentMessage]
    model: str | None = None


def _serialize(a: Agent) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "prompt_id": a.prompt_id,
        "knowledge_base_id": a.knowledge_base_id,
        "created_at": a.created_at.isoformat(),
    }


@router.get("")
async def list_agents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Agent).where(Agent.user_id == current_user.id).order_by(Agent.created_at.desc())
    )
    return [_serialize(a) for a in result.scalars().all()]


@router.post("")
async def create_agent(
    body: AgentPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = body.name.strip()
    prompt_id = body.prompt_id.strip()
    knowledge_base_id = body.knowledge_base_id.strip()
    if not name or not prompt_id or not knowledge_base_id:
        raise HTTPException(status_code=400, detail="Name, prompt_id and knowledge_base_id are required.")

    prompt_exists = await db.execute(
        select(Prompt.id).where(Prompt.id == prompt_id, Prompt.user_id == current_user.id)
    )
    if prompt_exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Prompt not found.")

    agent = Agent(
        name=name,
        prompt_id=prompt_id,
        knowledge_base_id=knowledge_base_id,
        user_id=current_user.id,
    )
    db.add(agent)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="An agent with this name already exists.")
    await db.refresh(agent)
    return _serialize(agent)


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        delete(Agent).where(Agent.id == agent_id, Agent.user_id == current_user.id)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Agent not found.")
    await db.commit()
    return {"id": agent_id, "deleted": True}


@router.post("/{agent_id}/stream")
async def stream_agent(
    agent_id: str,
    req: AgentStreamRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")

    prompt_result = await db.execute(
        select(Prompt.content).where(Prompt.id == agent.prompt_id, Prompt.user_id == current_user.id)
    )
    system_prompt = prompt_result.scalar_one_or_none()
    if not system_prompt:
        raise HTTPException(status_code=404, detail="Agent prompt not found.")

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
            logging.exception("RAG retrieval failed (agent=%s, kb=%s)", agent.id, agent.knowledge_base_id)

    messages = [{"role": "system", "content": system_prompt + rag_context}] + [m.model_dump() for m in req.messages]
    provider = get_provider(req.model)

    def event_stream():
        if hits:
            sources = [{"source": h["source"], "page": h["page"], "score": h.get("score")} for h in hits]
            yield f"event: sources\ndata: {json.dumps(sources)}\n\n"
        for token in provider.stream(messages):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")