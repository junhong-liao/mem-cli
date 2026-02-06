from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.tools import tool

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
from cli_core.lt_memory import JsonlLongTermMemoryStore
from cli_core.providers.base import MissingEnvError

DEFAULT_USER_ID = "default-user"
DEFAULT_THREAD_ID = "default-thread"
ENV_OVERRIDE_VAR = "MEMCLI_ENV_PATH"
CHECKPOINT_DB = Path("data/checkpoints.sqlite")
LT_MEMORY_DIR = Path("data/memory")
LT_RETRIEVAL_K = 3
SESSION_SHOW_LIMIT = 12
MEMORY_SHOW_LIMIT = 12
SHOW_CONTENT_PREVIEW_CHARS = 160


def build_prompt(context: RuntimeContext) -> str:
    state = context.state if isinstance(context.state, dict) else {}
    records = state.get("lt_recent_records", [])
    memory_lines = []
    for record in records:
        content = str(record.get("content", "")).strip()
        if not content:
            continue
        kind = str(record.get("kind", "semantic")).strip() or "semantic"
        memory_lines.append(f"- [{kind}] {content}")
    known_memory_block = "\n".join(memory_lines) if memory_lines else "(none)"
    return (
        "You are a helpful assistant. Keep answers concise unless asked to expand.\n"
        "Use the conversation history to resolve follow-ups and pronouns.\n\n"
        "You may call tool `memory_upsert` to store durable user facts/preferences/"
        "constraints for future sessions. Only store stable information likely useful "
        "later. Do not store one-off chatter, transient requests, or uncertain facts.\n\n"
        "Known memory (optional context, may be stale):\n"
        f"{known_memory_block}"
    )


def _load_identity() -> dict[str, str]:
    return {
        "user_id": os.environ.get("MEMCLI_USER_ID", DEFAULT_USER_ID),
        "thread_id": os.environ.get("MEMCLI_THREAD_ID", DEFAULT_THREAD_ID),
    }


def _clear_session_state(context: RuntimeContext) -> str:
    state = context.state if isinstance(context.state, dict) else {}
    identity = state.get("identity", {})
    thread_id = identity.get("thread_id", DEFAULT_THREAD_ID)
    store = state.get("checkpoint_store")

    context.history = []
    if store is not None and hasattr(store, "clear"):
        try:
            cleared = bool(store.clear(thread_id))
        except Exception as exc:  # noqa: BLE001
            return f"Session clear warning for active thread: {exc}"
        if cleared:
            return "Session cleared for active thread."
    return "Session already clear for active thread (no session state to remove)."


def _clear_memory_state(context: RuntimeContext) -> str:
    state = context.state if isinstance(context.state, dict) else {}
    identity = state.get("identity", {})
    user_id = identity.get("user_id", DEFAULT_USER_ID)
    store = state.get("lt_store")
    if store is None or not hasattr(store, "clear"):
        return "Memory already clear for active user (no persisted memory to remove)."

    try:
        cleared = bool(store.clear(user_id))
    except Exception as exc:  # noqa: BLE001
        return f"Memory clear warning for active user: {exc}"

    state["lt_recent_records"] = []
    context.state = state
    if not cleared:
        return "Memory already clear for active user (no persisted memory to remove)."
    return "Memory cleared for active user."


def _handle_session_clear(context: RuntimeContext, _raw: str) -> bool:
    print(_clear_session_state(context))
    return True


def _handle_memory_clear(context: RuntimeContext, _raw: str) -> bool:
    print(_clear_memory_state(context))
    return True


def _clip_text(value: Any, limit: int = SHOW_CONTENT_PREVIEW_CHARS) -> str:
    flattened = " ".join(str(value).split())
    if len(flattened) <= limit:
        return flattened
    return f"{flattened[: limit - 3]}..."


def _message_role(message: BaseMessage) -> str:
    role = getattr(message, "type", "message")
    if role == "human":
        return "user"
    if role == "ai":
        return "assistant"
    if role == "tool":
        return "tool"
    return str(role)


def _session_show_text(context: RuntimeContext) -> str:
    state = context.state if isinstance(context.state, dict) else {}
    identity = state.get("identity", {})
    thread_id = identity.get("thread_id", DEFAULT_THREAD_ID)
    history = context.history if isinstance(context.history, list) else []
    if not history:
        return f"Session empty for active thread (thread_id={thread_id})."

    tail = history[-SESSION_SHOW_LIMIT:]
    start_index = len(history) - len(tail) + 1
    lines = [
        (
            f"Session view for active thread (thread_id={thread_id}) "
            f"showing_last={len(tail)} total_messages={len(history)} "
            f"limit={SESSION_SHOW_LIMIT}:"
        )
    ]
    for idx, message in enumerate(tail, start=start_index):
        role = _message_role(message)
        lines.append(
            f"{idx:03d} [{role}] {_clip_text(getattr(message, 'content', ''))}"
        )
    return "\n".join(lines)


def _memory_show_text(context: RuntimeContext) -> str:
    state = context.state if isinstance(context.state, dict) else {}
    identity = state.get("identity", {})
    user_id = identity.get("user_id", DEFAULT_USER_ID)
    store = state.get("lt_store")

    if store is None or not hasattr(store, "load_recent"):
        return f"Memory empty for active user (user_id={user_id})."

    records = store.load_recent(user_id, k=MEMORY_SHOW_LIMIT)
    if not records:
        return f"Memory empty for active user (user_id={user_id})."

    lines = [
        (
            f"Memory view for active user (user_id={user_id}) "
            f"showing_latest={len(records)} limit={MEMORY_SHOW_LIMIT} "
            "(order=newest-first):"
        )
    ]
    for idx, record in enumerate(records, start=1):
        lines.append(
            (
                f"{idx:02d} id={record.get('id', '-')}"
                f" kind={record.get('kind', '-')}"
                f" updated_at={record.get('updated_at', '-')}"
                f" source_turn_id={record.get('source_turn_id', '-')}"
                f" content={_clip_text(record.get('content', ''))}"
            )
        )
    return "\n".join(lines)


def _handle_session_show(context: RuntimeContext, _raw: str) -> bool:
    try:
        print(_session_show_text(context))
    except Exception as exc:  # noqa: BLE001
        print(f"Session show warning for active thread: {_clip_text(exc, limit=180)}")
    return True


def _handle_memory_show(context: RuntimeContext, _raw: str) -> bool:
    try:
        print(_memory_show_text(context))
    except Exception as exc:  # noqa: BLE001
        print(f"Memory show warning for active user: {_clip_text(exc, limit=180)}")
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
    restored = len(context.history)
    print(f"identity user_id={user_id} thread_id={thread_id}")
    print(f"session restored_messages={restored}")
    print("commands: /session-clear /memory-clear /reset /paste /exit")
    print("inspect: /session-show /memory-show")


def _on_after_turn(context: RuntimeContext, _new_messages) -> None:
    state = context.state if isinstance(context.state, dict) else {}
    identity = state.get("identity", {})
    thread_id = identity.get("thread_id", DEFAULT_THREAD_ID)
    store = state.get("checkpoint_store")
    if store is None or not hasattr(store, "save"):
        return
    try:
        store.save(thread_id, context.history)
    except Exception as exc:  # noqa: BLE001
        print(
            "Checkpoint write error for this turn. "
            f"Your response was produced but session state was not persisted: {exc}"
        )


def _on_before_turn(context: RuntimeContext, _user_text: str) -> None:
    state = context.state if isinstance(context.state, dict) else {}
    identity = state.get("identity", {})
    user_id = identity.get("user_id", DEFAULT_USER_ID)
    thread_id = identity.get("thread_id", DEFAULT_THREAD_ID)
    state["turn_counter"] = int(state.get("turn_counter", 0)) + 1
    state["active_turn_id"] = f"{thread_id}:{state['turn_counter']}"
    state["turn_memory_write_count"] = 0

    store = state.get("lt_store")
    if store is None or not hasattr(store, "load_recent"):
        state["lt_recent_records"] = []
        context.state = state
        return

    try:
        state["lt_recent_records"] = store.load_recent(user_id, k=LT_RETRIEVAL_K)
    except Exception as exc:  # noqa: BLE001
        print(f"Long-term memory retrieval warning for active user: {exc}")
        state["lt_recent_records"] = []
    context.state = state


def _build_memory_upsert_tool(
    state: dict[str, Any],
    store: JsonlLongTermMemoryStore,
):
    @tool
    def memory_upsert(
        content: str,
        kind: str = "semantic",
        confidence: float | None = None,
        source_turn_id: str | None = None,
    ) -> str:
        """Store durable user memory for use across sessions.

        Save only stable user facts/preferences/constraints likely useful in future turns.
        Skip one-off chatter, transient requests, and uncertain information.
        """

        cleaned = content.strip()
        if not cleaned:
            return "Memory write skipped: content is empty."

        identity = state.get("identity", {})
        user_id = identity.get("user_id", DEFAULT_USER_ID)
        turn_id = source_turn_id or str(state.get("active_turn_id", "")).strip() or None
        memory_kind = kind.strip() or "semantic"
        try:
            record = store.append(
                user_id=user_id,
                content=cleaned,
                kind=memory_kind,
                confidence=confidence,
                source_turn_id=turn_id,
            )
        except Exception as exc:  # noqa: BLE001
            return (
                "Memory write failed for active user. "
                f"The session will continue without durable memory for this turn: {exc}"
            )
        return (
            f"Memory saved for active user. id={record['id']} "
            f"kind={record['kind']}."
        )

    return memory_upsert


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
    try:
        from cli_core.checkpoints import SqliteCheckpointStore
    except ModuleNotFoundError as exc:
        print(
            "Configuration error: missing dependency for checkpoint persistence. "
            "Install requirements with `pip install -r requirements.txt`."
        )
        print(f"Detail: {exc}")
        sys.exit(1)

    checkpoint_store = SqliteCheckpointStore(repo_root / CHECKPOINT_DB)
    lt_store = JsonlLongTermMemoryStore(repo_root / LT_MEMORY_DIR)
    state: dict[str, Any] = {
        "identity": _load_identity(),
        "checkpoint_store": checkpoint_store,
        "lt_store": lt_store,
        "lt_recent_records": [],
    }
    tools.register(_build_memory_upsert_tool(state, lt_store))
    thread_id = state["identity"]["thread_id"]
    try:
        state["restored_from_checkpoint"] = checkpoint_store.load(thread_id)
    except Exception as exc:  # noqa: BLE001
        print(f"Checkpoint load warning for active thread: {exc}")
        state["restored_from_checkpoint"] = []

    options = RuntimeOptions(
        prompt_builder=build_prompt,
        tool_registry=tools,
        command_handlers={
            "/session-clear": _handle_session_clear,
            "/memory-clear": _handle_memory_clear,
            "/session-show": _handle_session_show,
            "/memory-show": _handle_memory_show,
        },
        on_start=_on_start,
        on_reset=_handle_reset,
        on_before_turn=_on_before_turn,
        on_after_turn=_on_after_turn,
        renderer=RendererConfig(assistant_label="Agent", user_label="You"),
        trace_requests=trace_enabled,
    )
    print(f"mem-cli [{adapter.system_label()}]")
    run_cli(
        adapter,
        options,
        state=state,
        initial_history=state.get("restored_from_checkpoint", []),
    )


if __name__ == "__main__":
    main()
