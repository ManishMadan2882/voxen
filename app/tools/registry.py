from typing import Type

from tools.base import ToolProvider

_REGISTRY: dict[str, Type[ToolProvider]] = {}


def register_provider(cls: Type[ToolProvider]) -> Type[ToolProvider]:
    if not cls.type_name:
        raise ValueError(f"{cls.__name__} must set type_name to register.")
    _REGISTRY[cls.type_name] = cls
    return cls


def get_provider_class(type_name: str) -> Type[ToolProvider] | None:
    return _REGISTRY.get(type_name)


def list_provider_types() -> list[str]:
    return sorted(_REGISTRY.keys())


def build_provider(type_name: str, config: dict) -> ToolProvider:
    cls = get_provider_class(type_name)
    if cls is None:
        raise ValueError(f"Unknown tool provider type: {type_name}")
    return cls(config)