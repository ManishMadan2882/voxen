from fastapi import FastAPI, HTTPException
from uuid import uuid4
from datetime import datetime

from app.core import handle_turn
from app.models import TurnRequest
from app.state import sessions, orders, knowledge, llm_client
from app.streaming import router as streaming_router

app = FastAPI(title="Telephony Agent Prototype")
app.include_router(streaming_router)


@app.get("/health")
def health():
    return {"ok": True, "sessions": len(sessions)}


@app.post("/call/start")
def start_call():
    session_id = str(uuid4())
    sessions[session_id] = {
        "id": session_id,
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "verified": False,
        "lastIntent": None,
    }
    return {
        "sessionId": session_id,
        "prompt": "Thanks for calling. How can I help you today?",
    }


@app.post("/call/turn")
def turn(req: TurnRequest):
    if req.sessionId not in sessions:
        raise HTTPException(status_code=400, detail="Invalid or missing sessionId.")

    session = sessions[req.sessionId]
    return handle_turn(
        text=req.text,
        session=session,
        orders=orders,
        knowledge=knowledge,
        llm_client=llm_client,
        order_id=req.orderId,
        last4=req.last4,
    )
