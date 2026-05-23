import json
import urllib.request
from typing import Iterator


class OllamaProvider:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip('/')
        self.model = model

    def stream(self, messages: list[dict], tools: list[dict] | None = None) -> Iterator[str]:
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": True,
            **({"tools": tools} if tools else {}),
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

    def generate(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
            **({"tools": tools} if tools else {}),
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        message = data.get("message") or {}
        return {
            "content": message.get("content") or "",
            "tool_calls": _normalise_tool_calls(message.get("tool_calls") or []),
        }


def _normalise_tool_calls(calls: list[dict]) -> list[dict]:
    normalised: list[dict] = []
    for call in calls:
        function = call.get("function") or call
        name = function.get("name") or call.get("name")
        if not name:
            continue
        args = function.get("arguments") or call.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        if not isinstance(args, dict):
            args = {}
        normalised.append({"id": call.get("id"), "name": name, "arguments": args})
    return normalised
