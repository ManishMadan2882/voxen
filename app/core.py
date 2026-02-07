from typing import Any, Dict, Optional

from app.exceptions import LLMError
from app.llm import LLMClient


def detect_intent(text: str) -> str:
    t = text.lower()
    if "order" in t or "tracking" in t or "status" in t:
        return "order_status"
    if "return" in t or "refund" in t:
        return "return_policy"
    if "verify" in t or "account" in t or "identity" in t:
        return "account_verify"
    if "agent" in t or "human" in t or "representative" in t:
        return "live_agent"
    return "fallback"


def get_order_status(orders, order_id: str):
    for order in orders:
        if order.get("orderId") == order_id:
            return order
    return None


def handle_turn(
    *,
    text: str,
    session: Dict[str, Any],
    orders,
    knowledge,
    llm_client: LLMClient,
    order_id: Optional[str] = None,
    last4: Optional[str] = None,
) -> Dict[str, Any]:
    intent = detect_intent(text)
    session["lastIntent"] = intent

    if llm_client.enabled:
        try:
            llm_reply = llm_client.respond(
                text=text,
                intent=intent,
                session=session,
                order_id=order_id,
                last4=last4,
            )
            if llm_reply:
                return llm_reply
        except LLMError:
            # Fall back to deterministic rules if LLM fails.
            pass

    if intent == "order_status":
        if not order_id:
            return {"intent": intent, "prompt": "Sure. What is your order ID?"}
        order = get_order_status(orders, order_id)
        if not order:
            return {
                "intent": intent,
                "prompt": f"I could not find order {order_id}. Could you confirm the ID?",
            }
        return {
            "intent": intent,
            "prompt": f"Order {order_id} is {order['status']}. Estimated delivery: {order['eta']}.",
        }

    if intent == "return_policy":
        return {"intent": intent, "prompt": knowledge["returnPolicy"]}

    if intent == "account_verify":
        if not last4:
            return {
                "intent": intent,
                "prompt": "Please provide the last 4 digits of the phone number on the account.",
            }
        if len(str(last4)) != 4:
            return {
                "intent": intent,
                "prompt": "That does not look like 4 digits. Please provide the last 4 digits.",
            }
        session["verified"] = True
        return {"intent": intent, "prompt": "Thanks, you are verified. How else can I help?"}

    if intent == "live_agent":
        return {
            "intent": intent,
            "prompt": "Connecting you to a live agent now.",
            "handoff": True,
            "transcriptSnippet": text,
        }

    return {
        "intent": "fallback",
        "prompt": "I can help with order status, returns, or account verification. Which would you like?",
    }
