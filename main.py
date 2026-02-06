from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from cli_core import (
    RendererConfig,
    RuntimeContext,
    RuntimeOptions,
    ToolRegistry,
    create_adapter,
    is_env_enabled,
    load_env,
    log_env_loaded,
    run_cli,
)
from cli_core.providers.base import MissingEnvError

DEFAULT_USER_ID = "default-user"
DEFAULT_THREAD_ID = "default-thread"
ENV_OVERRIDE_VAR = "MEMCLI_ENV_PATH"


def build_prompt(_context) -> str:
    return (
        "You are a helpful assistant. Keep answers concise unless asked to expand.\n"
        "Use the conversation history to resolve follow-ups and pronouns."
    )


def _load_identity() -> dict[str, str]:
    return {
        "user_id": os.environ.get("MEMCLI_USER_ID", DEFAULT_USER_ID),
        "thread_id": os.environ.get("MEMCLI_THREAD_ID", DEFAULT_THREAD_ID),
    }


def _clear_session_state(context: RuntimeContext) -> str:
    # Stage 1 hook: ST checkpoint internals are added in later stages.
    if context.history:
        context.history = []
        return "Session cleared for active thread."
    return "Session already clear for active thread (no session state to remove)."


def _clear_memory_state(context: RuntimeContext) -> str:
    # Stage 1 hook: LT storage internals are added in later stages.
    state = context.state if isinstance(context.state, dict) else {}
    if state.get("memory_cleared", False):
        return "Memory already clear for active user (no persisted memory to remove)."
    state["memory_cleared"] = True
    context.state = state
    return "Memory cleared for active user."


def _handle_session_clear(context: RuntimeContext, _raw: str) -> bool:
    print(_clear_session_state(context))
    return True


def _handle_memory_clear(context: RuntimeContext, _raw: str) -> bool:
    print(_clear_memory_state(context))
    return True


def _handle_reset(context: RuntimeContext) -> str:
    session_message = _clear_session_state(context)
    memory_message = _clear_memory_state(context)
    return f"Reset complete. {session_message} {memory_message}"


def _on_start(context: RuntimeContext) -> None:
    state = context.state if isinstance(context.state, dict) else {}
    identity = state.get("identity", {})
    user_id = identity.get("user_id", DEFAULT_USER_ID)
    thread_id = identity.get("thread_id", DEFAULT_THREAD_ID)
    print(f"identity user_id={user_id} thread_id={thread_id}")
    print("commands: /session-clear /memory-clear /reset /paste /exit")


def main() -> None:
    trace_enabled = is_env_enabled(["CLI_TRACE_REQUEST"])
    repo_root = Path(__file__).resolve().parent
    env_path = load_env(ENV_OVERRIDE_VAR, start=repo_root, names=(".env",))
    env_source = "override" if os.environ.get(ENV_OVERRIDE_VAR) else "repo-local"
    log_env_loaded(env_path, env_source, trace_enabled)
    repo_env_path = repo_root / ".env"

    try:
        adapter = create_adapter(os.environ.get("MEMCLI_PROVIDER"))
    except MissingEnvError as exc:
        print(
            "Configuration error: missing MOONSHOT_API_KEY. "
            f"Set it in {repo_env_path} or pass an explicit env file path via MEMCLI_ENV_PATH."
        )
        print(f"Detail: {exc}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"Configuration error: {exc}")
        sys.exit(1)

    tools = ToolRegistry()
    state: dict[str, Any] = {
        "identity": _load_identity(),
        "memory_cleared": False,
    }
    options = RuntimeOptions(
        prompt_builder=build_prompt,
        tool_registry=tools,
        command_handlers={
            "/session-clear": _handle_session_clear,
            "/memory-clear": _handle_memory_clear,
        },
        on_start=_on_start,
        on_reset=_handle_reset,
        renderer=RendererConfig(assistant_label="Agent", user_label="You"),
        trace_requests=trace_enabled,
    )
    print(f"mem-cli [{adapter.system_label()}]")
    run_cli(adapter, options, state=state)


if __name__ == "__main__":
    main()
