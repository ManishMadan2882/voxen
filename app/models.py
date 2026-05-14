from typing import Literal
from pydantic import BaseModel


class Message(BaseModel):
    role: Literal['user', 'assistant', 'system']
    content: str


class StreamRequest(BaseModel):
    messages: list[Message]
    model: str | None = None
    ids: list[str] | None = None
    prompt_id: str | None = None
