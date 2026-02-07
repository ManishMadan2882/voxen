import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.exceptions import LLMError
from app.providers.ollama import OllamaProvider
from app.providers.gemini import GeminiProvider


@dataclass
class LLMConfig:
    provider: str
    model: str
    enabled: bool
    ollama_url: str
    gemini_api_key: Optional[str]

    @staticmethod
    def from_env() -> "LLMConfig":
        provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
        model = os.getenv("LLM_MODEL", "gemma3").strip()
        enabled = os.getenv("LLM_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate").strip()
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        return LLMConfig(
            provider=provider,
            model=model,
            enabled=enabled,
            ollama_url=ollama_url,
            gemini_api_key=gemini_api_key,
        )


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.enabled = config.enabled

        self._provider = None
        if config.provider == "ollama":
            self._provider = OllamaProvider(config.ollama_url, config.model)
        elif config.provider == "gemini":
            self._provider = GeminiProvider(config.gemini_api_key, config.model)

    def respond(
        self,
        text: str,
        intent: str,
        session: Dict[str, Any],
        order_id: Optional[str],
        last4: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        if not self._provider:
            raise LLMError(f"Unknown LLM provider: {self.config.provider}")

        prompt = self._build_prompt(text, intent, session, order_id, last4)

        result = self._provider.generate(prompt)
        response_text = result.get("text", "").strip()
        return self._safe_parse_json(response_text)

    def _build_prompt(
        self,
        text: str,
        intent: str,
        session: Dict[str, Any],
        order_id: Optional[str],
        last4: Optional[str],
    ) -> str:
        context = {
            "intent": intent,
            "orderId": order_id,
            "last4": last4,
            "verified": session.get("verified", False),
        }
        return (
            "You are a concise customer service voice agent. "
            "Return JSON only. \n"
            "Schema: {intent: string, prompt: string, handoff?: boolean}\n"
            f"Context: {json.dumps(context)}\n"
            f"User: {text}\n"
        )

    def _safe_parse_json(self, text: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(text)
        except Exception as exc:
            raise LLMError(f"LLM response was not valid JSON: {exc}")

        if not isinstance(parsed, dict) or "prompt" not in parsed:
            raise LLMError("LLM response missing required fields")
        return parsed
