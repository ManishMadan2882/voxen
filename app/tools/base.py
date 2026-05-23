from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {"type": "object", "properties": {}},
            },
        }


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str | None = None


@dataclass(frozen=True)
class ToolResult:
    call_id: str | None
    name: str
    content: str
    is_error: bool = False


class ToolProvider(ABC):
    type_name: str = ""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    def get_tools(self) -> list[ToolSpec]:
        ...

    @abstractmethod
    def execute(self, call: ToolCall) -> ToolResult:
        ...

    def owns(self, tool_name: str) -> bool:
        return any(spec.name == tool_name for spec in self.get_tools())