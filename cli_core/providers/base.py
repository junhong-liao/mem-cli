from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Protocol

from langchain_core.messages import BaseMessage


@dataclass
class ProviderConfig:
    name: str
    api_key: str
    model: str
    base_url: str | None = None
    extra_body: Dict[str, Any] | None = None


class ProviderAdapter(Protocol):
    name: str
    config: ProviderConfig

    def build_model(self) -> Any:
        ...

    def bind_tools(self, model: Any, tools: List[Any]) -> Any:
        ...

    def system_label(self) -> str:
        return self.name


def normalize_provider_name(value: str | None) -> str:
    if not value:
        return "moonshot"
    normalized = value.strip().lower()
    if normalized == "kimi":
        return "moonshot"
    return normalized


class MissingDependencyError(RuntimeError):
    pass


class MissingEnvError(RuntimeError):
    pass


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingEnvError(f"Missing required env var: {name}")
    return value
