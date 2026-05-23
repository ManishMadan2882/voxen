import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.agent_model import Agent
from agents.tool_model import AgentTool
from tools import ToolProvider, build_provider

logger = logging.getLogger(__name__)


async def load_agent_tool_providers(db: AsyncSession, agent: Agent) -> list[ToolProvider]:
    result = await db.execute(
        select(AgentTool)
        .where(AgentTool.agent_id == agent.id, AgentTool.is_active.is_(True))
        .order_by(AgentTool.created_at.asc())
    )
    providers: list[ToolProvider] = []
    for tool in result.scalars().all():
        try:
            providers.append(build_provider(tool.type, tool.config or {}))
        except Exception:
            logger.exception("Skipping invalid agent tool %s on agent %s", tool.id, agent.id)
    return providers