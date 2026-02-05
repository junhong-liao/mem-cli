from __future__ import annotations

from typing import Optional

from .base import MissingDependencyError, MissingEnvError, ProviderAdapter, ProviderConfig
from .moonshot import MoonshotAdapter


def create_adapter(_provider_name: Optional[str] = None) -> ProviderAdapter:
    return MoonshotAdapter()


__all__ = [
    "ProviderAdapter",
    "ProviderConfig",
    "MissingDependencyError",
    "MissingEnvError",
    "create_adapter",
    "MoonshotAdapter",
]
