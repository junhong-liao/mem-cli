from __future__ import annotations

import sys
from pathlib import Path

from cli_core import RendererConfig, RuntimeOptions, ToolRegistry, create_adapter, load_env, run_cli


def build_prompt(_context) -> str:
    return (
        "You are a helpful assistant. Keep answers concise unless asked to expand.\n"
        "Use the conversation history to resolve follow-ups and pronouns."
    )


def main() -> None:
    load_env(None, start=Path.cwd())
    try:
        adapter = create_adapter()
    except Exception as exc:  # noqa: BLE001
        print(f"Configuration error: {exc}")
        sys.exit(1)

    tools = ToolRegistry()
    options = RuntimeOptions(
        prompt_builder=build_prompt,
        tool_registry=tools,
        renderer=RendererConfig(assistant_label="Assistant"),
    )
    run_cli(adapter, options)


if __name__ == "__main__":
    main()
