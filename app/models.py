from pydantic import BaseModel


class TurnRequest(BaseModel):
    sessionId: str
    text: str
    orderId: str | None = None
    last4: str | None = None
