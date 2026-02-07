import json
import urllib.request
from typing import Any, Dict

from app.exceptions import LLMError


class OllamaProvider:
    def __init__(self, url: str, model: str):
        self.url = url
        self.model = model

    def generate(self, prompt: str) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise LLMError(str(exc))

        response_text = result.get("response", "").strip()
        if not response_text:
            raise LLMError("Ollama returned empty response")
        return {"text": response_text}
