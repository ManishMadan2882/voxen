from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from prompts.prompt_model import Prompt

router = APIRouter(prefix="/prompts")


class PromptPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)


def _serialize(p: Prompt) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "content": p.content,
        "created_at": p.created_at.isoformat(),
    }


@router.get("")
async def list_prompts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Prompt).order_by(Prompt.created_at.desc()))
    return [_serialize(p) for p in result.scalars().all()]


@router.post("")
async def create_prompt(body: PromptPayload, db: AsyncSession = Depends(get_db)):
    name = body.name.strip()
    content = body.content.strip()
    if not name or not content:
        raise HTTPException(status_code=400, detail="Name and content are required.")
    prompt = Prompt(name=name, content=content)
    db.add(prompt)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A prompt with this name already exists.")
    await db.refresh(prompt)
    return _serialize(prompt)


@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(Prompt).where(Prompt.id == prompt_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Prompt not found.")
    await db.commit()
    return {"id": prompt_id, "deleted": True}
