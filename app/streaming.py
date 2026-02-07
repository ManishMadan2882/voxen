import time
from typing import Iterable

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core import handle_turn
from app.models import TurnRequest
from app.state import sessions, orders, knowledge, llm_client

router = APIRouter()


def _chunk_text(text: str, size: int = 16) -> Iterable[str]:
    for i in range(0, len(text), size):
        yield text[i : i + size]


def handle_stream(req: TurnRequest):
    if req.sessionId not in sessions:
        raise HTTPException(status_code=400, detail="Invalid or missing sessionId.")

    session = sessions[req.sessionId]
    response = handle_turn(
        text=req.text,
        session=session,
        orders=orders,
        knowledge=knowledge,
        llm_client=llm_client,
        order_id=req.orderId,
        last4=req.last4,
    )

    prompt = response.get("prompt", "")

    def event_stream():
        yield "event: meta\n"
        yield f"data: {{\"intent\": \"{response.get('intent', 'fallback')}\"}}\n\n"
        for chunk in _chunk_text(prompt):
            yield "event: token\n"
            yield f"data: {chunk}\n\n"
            time.sleep(0.02)
        if response.get("handoff"):
            yield "event: handoff\n"
            yield "data: true\n\n"
        yield "event: done\n"
        yield "data: true\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/call/stream")
def stream(req: TurnRequest):
    return handle_stream(req)
