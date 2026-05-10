import json
import urllib.request
from typing import Iterator


class OllamaProvider:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip('/')
        self.model = model

    def stream(self, messages: list[dict]) -> Iterator[str]:
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": True,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            for line in resp:
                chunk = json.loads(line.decode())
                if token := chunk.get("message", {}).get("content"):
                    yield token
                if chunk.get("done"):
                    break
