import json
import logging
from typing import Iterator, Protocol

from tools.base import ToolCall, ToolProvider, ToolResult, ToolSpec

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5


class LLMProvider(Protocol):
    def stream(self, messages: list[dict], tools: list[dict] | None = ...) -> Iterator[str]:
        ...

    def generate(self, messages: list[dict], tools: list[dict] | None = ...) -> dict:
        ...


class ResponseOrchestrator:
    def __init__(
        self,
        provider: LLMProvider,
        tool_providers: list[ToolProvider] | None = None,
        max_iterations: int = MAX_TOOL_ITERATIONS,
    ):
        self.provider = provider
        self.max_iterations = max_iterations
        self._by_name: dict[str, ToolProvider] = {}
        self._specs: list[ToolSpec] = []
        for tool_provider in tool_providers or []:
            for spec in tool_provider.get_tools():
                if spec.name in self._by_name:
                    logger.warning("Duplicate tool name %s; later provider ignored.", spec.name)
                    continue
                self._by_name[spec.name] = tool_provider
                self._specs.append(spec)

    def stream(self, messages: list[dict]) -> Iterator[str]:
        if not self._specs:
            yield from self.provider.stream(messages)
            return

        working = [dict(m) for m in messages]
        tool_payload = [spec.to_openai() for spec in self._specs]
        for _ in range(self.max_iterations):
            result = self.provider.generate(working, tools=tool_payload)
            calls = result.get("tool_calls") or []
            if not calls:
                yield from self.provider.stream(working)
                return

            working.append({
                "role": "assistant",
                "content": result.get("content") or "",
                "tool_calls": [_serialise_call(c) for c in calls],
            })
            for c in calls:
                arguments = c.get("arguments") or {}
                if not isinstance(arguments, dict):
                    arguments = {}
                tool_call = ToolCall(
                    name=c["name"],
                    arguments=arguments,
                    call_id=c.get("id"),
                )
                tool_result = self._dispatch(tool_call)
                working.append({
                    "role": "tool",
                    "tool_call_id": tool_result.call_id or tool_call.name,
                    "name": tool_result.name,
                    "content": tool_result.content,
                })

        logger.warning("Tool loop hit max_iterations=%d; streaming final answer.", self.max_iterations)
        yield from self.provider.stream(working)

    def _dispatch(self, call: ToolCall) -> ToolResult:
        provider = self._by_name.get(call.name)
        if provider is None:
            return ToolResult(call.call_id, call.name, f"No provider for tool {call.name}", is_error=True)
        try:
            return provider.execute(call)
        except Exception as e:
            logger.exception("Tool %s raised", call.name)
            return ToolResult(call.call_id, call.name, f"Tool error: {e}", is_error=True)


def _serialise_call(c: dict) -> dict:
    return {
        "id": c.get("id"),
        "type": "function",
        "function": {
            "name": c["name"],
            "arguments": json.dumps(c.get("arguments") or {}),
        },
    }