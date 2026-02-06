from __future__ import annotations

from typing import Optional

from .base import (
    MissingDependencyError,
    MissingEnvError,
    ProviderAdapter,
    ProviderConfig,
    normalize_provider_name,
)
from .moonshot import MoonshotAdapter

_SUPPORTED_PROVIDER = "moonshot"
_KIMI_ALIASES = {"moonshot", "kimi"}


def create_adapter(provider_name: Optional[str] = None) -> ProviderAdapter:
    normalized = normalize_provider_name(provider_name)
    if normalized in _KIMI_ALIASES:
        return MoonshotAdapter()
    raise ValueError(
        f"Unsupported provider '{provider_name}'. mem-cli is Kimi-only; use provider '{_SUPPORTED_PROVIDER}'."
    )


__all__ = [
    "ProviderAdapter",
    "ProviderConfig",
    "MissingDependencyError",
    "MissingEnvError",
    "create_adapter",
    "MoonshotAdapter",
]
