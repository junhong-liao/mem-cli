from __future__ import annotations

from typing import Any, List

from langchain_openai import ChatOpenAI

from .base import ProviderAdapter, ProviderConfig, require_env


class MoonshotAdapter(ProviderAdapter):
    name = "moonshot"

    def __init__(self) -> None:
        thinking_env = __import__("os").environ.get(
            "MOONSHOT_THINKING", "disabled"
        ).strip().lower()
        extra_body = None
        if thinking_env in {"disabled", "off", "false", "0"}:
            extra_body = {"thinking": {"type": "disabled"}}
        elif thinking_env in {"enabled", "on", "true", "1"}:
            extra_body = {"thinking": {"type": "enabled"}}

        self.config = ProviderConfig(
            name="Kimi",
            api_key=require_env("MOONSHOT_API_KEY"),
            model=(
                __import__("os").environ.get("MOONSHOT_MODEL", "kimi-k2.5")
            ),
            base_url=__import__("os").environ.get(
                "MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1"
            ),
            extra_body=extra_body,
        )

    def build_model(self) -> Any:
        return ChatOpenAI(
            model=self.config.model,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            streaming=True,
            extra_body=self.config.extra_body,
        )

    def bind_tools(self, model: Any, tools: List[Any]) -> Any:
        return model.bind_tools(tools)

    def system_label(self) -> str:
        return self.config.name
