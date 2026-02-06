from __future__ import annotations

import sys
from pathlib import Path

from cli_core import (
    RendererConfig,
    RuntimeOptions,
    ToolRegistry,
    create_adapter,
    is_env_enabled,
    load_env,
    log_env_loaded,
    run_cli,
)


def build_prompt(_context) -> str:
    return (
        "You are a helpful assistant. Keep answers concise unless asked to expand.\n"
        "Use the conversation history to resolve follow-ups and pronouns."
    )


def main() -> None:
    trace_enabled = is_env_enabled(["CLI_TRACE_REQUEST"])
    env_path = load_env(None, start=Path.cwd())
    log_env_loaded(env_path, "auto", trace_enabled)
    try:
        adapter = create_adapter()
    except Exception as exc:  # noqa: BLE001
        print(f"Configuration error: {exc}")
        sys.exit(1)

    tools = ToolRegistry()
    options = RuntimeOptions(
        prompt_builder=build_prompt,
        tool_registry=tools,
        renderer=RendererConfig(assistant_label="Agent", user_label="You"),
        trace_requests=trace_enabled,
    )
    print(f"mem-cli [{adapter.system_label()}]")
    run_cli(adapter, options)


if __name__ == "__main__":
    main()
