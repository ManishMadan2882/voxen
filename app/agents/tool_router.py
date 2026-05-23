from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agents.agent_model import Agent
from agents.tool_model import AgentTool
from db import get_db
from tools import build_provider, list_provider_types
from users.auth import get_current_user
from users.user_model import User

router = APIRouter(prefix="/agents")

_SECRET_CONFIG_KEYS = {"authorization", "api_key", "x-api-key", "token", "secret", "password"}


class AgentToolPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: str = Field(min_length=1, max_length=60)
    config: dict = Field(default_factory=dict)
    is_active: bool = True


def _serialize(t: AgentTool) -> dict:
    return {
        "id": t.id,
        "agent_id": t.agent_id,
        "name": t.name,
        "type": t.type,
        "config": _redact_config(t.config or {}),
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat(),
    }


def _redact_config(value):
    if isinstance(value, dict):
        return {
            k: ("[redacted]" if k.lower() in _SECRET_CONFIG_KEYS else _redact_config(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_config(v) for v in value]
    return value


async def _ensure_agent(db: AsyncSession, agent_id: str, user_id: str) -> None:
    result = await db.execute(select(Agent.id).where(Agent.id == agent_id, Agent.user_id == user_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Agent not found.")


@router.get("/tool-types")
def get_tool_types():
    return {"types": list_provider_types()}


@router.get("/{agent_id}/tools")
async def list_agent_tools(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _ensure_agent(db, agent_id, current_user.id)
    result = await db.execute(
        select(AgentTool)
        .where(AgentTool.agent_id == agent_id)
        .order_by(AgentTool.created_at.desc())
    )
    return [_serialize(t) for t in result.scalars().all()]


@router.post("/{agent_id}/tools", status_code=201)
async def create_agent_tool(
    agent_id: str,
    body: AgentToolPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _ensure_agent(db, agent_id, current_user.id)
    try:
        build_provider(body.type, body.config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid tool config: {e}")

    tool = AgentTool(
        agent_id=agent_id,
        user_id=current_user.id,
        name=body.name.strip(),
        type=body.type,
        config=body.config,
        is_active=body.is_active,
    )
    db.add(tool)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A tool with this name already exists on the agent.")
    await db.refresh(tool)
    return _serialize(tool)


@router.delete("/{agent_id}/tools/{tool_id}")
async def delete_agent_tool(
    agent_id: str,
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _ensure_agent(db, agent_id, current_user.id)
    result = await db.execute(
        delete(AgentTool).where(
            AgentTool.id == tool_id,
            AgentTool.agent_id == agent_id,
            AgentTool.user_id == current_user.id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Tool not found.")
    await db.commit()
    return {"id": tool_id, "deleted": True}