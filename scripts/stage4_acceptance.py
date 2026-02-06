from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Iterable, List
from unittest.mock import patch

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from cli_core.checkpoints import SqliteCheckpointStore
from cli_core.lt_memory import JsonlLongTermMemoryStore
from cli_core.runtime import RuntimeOptions, run_cli, stream_model_turn
from cli_core.tools import ToolRegistry


ROOT = Path(__file__).resolve().parents[1]


class CheckFailed(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


class FakeBoundModel:
    def __init__(self, fail_first_stream: bool = False) -> None:
        self.fail_first_stream = fail_first_stream
        self.stream_calls = 0

    def stream(self, _messages: List[Any], config: dict[str, Any] | None = None):
        _ = config
        self.stream_calls += 1
        if self.fail_first_stream and self.stream_calls == 1:
            raise RuntimeError("forced stream failure for harness")
        yield AIMessageChunk(content="Recovered response")


class FakeAdapter:
    name = "moonshot"

    def __init__(self, bound_model: FakeBoundModel) -> None:
        self.bound_model = bound_model
        self.build_calls = 0
        self.bind_calls = 0
        self.config = type("Config", (), {"model": "fake-model"})()

    def build_model(self) -> Any:
        self.build_calls += 1
        return object()

    def bind_tools(self, _model: Any, _tools: List[Any]) -> Any:
        self.bind_calls += 1
        return self.bound_model

    def system_label(self) -> str:
        return "Kimi"


class FakeIndicatorThread:
    def __init__(self) -> None:
        self.join_calls = 0

    def join(self, timeout: float | None = None) -> None:
        _ = timeout
        self.join_calls += 1


def check_startup_command_surface() -> tuple[bool, str]:
    env = os.environ.copy()
    env["MOONSHOT_API_KEY"] = env.get("MOONSHOT_API_KEY", "dummy-stage4-key")
    proc = subprocess.run(
        [sys.executable, "main.py"],
        cwd=ROOT,
        input="/exit\n",
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    output = proc.stdout + proc.stderr
    ok = (
        proc.returncode == 0
        and "commands: /session-clear /memory-clear /reset /paste /exit" in output
    )
    return ok, output


def check_spinner_cleanup_on_stream_failure() -> tuple[bool, str]:
    events = []
    threads: List[FakeIndicatorThread] = []

    def fake_start_thinking_indicator(stop_event):
        events.append(stop_event)
        thread = FakeIndicatorThread()
        threads.append(thread)
        return thread

    bound_model = FakeBoundModel(fail_first_stream=True)
    with patch("cli_core.runtime.start_thinking_indicator", fake_start_thinking_indicator):
        try:
            _ = stream_model_turn(bound_model, [HumanMessage(content="hello")])
            return False, "expected stream_model_turn to raise on forced failure"
        except RuntimeError as exc:
            error = str(exc)

    require(events, "spinner event was not created")
    require(threads, "spinner indicator thread was not created")
    require(events[0].is_set(), "spinner stop_event was not set on failure path")
    require(threads[0].join_calls == 1, "spinner thread join was not called exactly once")
    return True, f"caught={error}; stop_event_set={events[0].is_set()}; join_calls={threads[0].join_calls}"


def check_turn_failure_recovery_and_model_reuse() -> tuple[bool, str]:
    bound_model = FakeBoundModel(fail_first_stream=True)
    adapter = FakeAdapter(bound_model)
    options = RuntimeOptions(
        prompt_builder=lambda _context: "You are a helpful assistant.",
        tool_registry=ToolRegistry(),
    )

    scripted_inputs = iter(["hello", "hello again", "/exit"])
    stdout = io.StringIO()
    with (
        patch("builtins.input", side_effect=lambda _prompt="": next(scripted_inputs)),
        redirect_stdout(stdout),
    ):
        run_cli(adapter=adapter, options=options, state={}, initial_history=[])

    output = stdout.getvalue()
    require(
        "Turn error: model invocation failed." in output,
        "turn failure did not emit actionable error",
    )
    require(
        "Recovered response" in output,
        "CLI did not remain usable for subsequent turn after forced failure",
    )
    require(
        adapter.build_calls == 1 and adapter.bind_calls == 1,
        "model was rebuilt/rebound more than once in one CLI session",
    )
    return (
        True,
        (
            f"build_calls={adapter.build_calls}, bind_calls={adapter.bind_calls}, "
            f"stream_calls={bound_model.stream_calls}"
        ),
    )


def check_stage2_st_restore_isolation() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "checkpoints.sqlite"
        store = SqliteCheckpointStore(db_path)
        t1 = [HumanMessage(content="hello"), AIMessage(content="t1-state")]
        t2 = [HumanMessage(content="hola"), AIMessage(content="t2-state")]
        store.save("thread-a", t1)
        store.save("thread-b", t2)

        loaded_a = store.load("thread-a")
        loaded_b = store.load("thread-b")
        require(len(loaded_a) == 2 and loaded_a[-1].content == "t1-state", "thread-a restore failed")
        require(len(loaded_b) == 2 and loaded_b[-1].content == "t2-state", "thread-b restore failed")
        require(loaded_a[-1].content != loaded_b[-1].content, "thread isolation failed")

        first_clear = store.clear("thread-a")
        second_clear = store.clear("thread-a")
        require(first_clear is True and second_clear is False, "thread clear idempotency failed")
        require(store.load("thread-a") == [], "cleared thread still has state")
        require(store.load("thread-b")[-1].content == "t2-state", "clear leaked to other thread")

    return True, "restore/isolation/clear-idempotent verified"


def check_stage3_lt_restore_isolation_clear() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        store = JsonlLongTermMemoryStore(Path(tmp) / "memory")
        store.append("user-a", "likes tea", kind="semantic")
        store.append("user-a", "uses vim", kind="semantic")
        store.append("user-b", "likes coffee", kind="semantic")

        recent_a = store.load_recent("user-a", k=3)
        recent_b = store.load_recent("user-b", k=3)
        require(len(recent_a) == 2, "user-a LT restore failed")
        require(len(recent_b) == 1, "user-b LT restore failed")
        require(
            all(record["user_id"] == "user-a" for record in recent_a),
            "LT user isolation failed for user-a load",
        )
        require(
            all(record["user_id"] == "user-b" for record in recent_b),
            "LT user isolation failed for user-b load",
        )

        first_clear = store.clear("user-a")
        second_clear = store.clear("user-a")
        require(first_clear is True and second_clear is False, "LT clear idempotency failed")
        require(store.load_recent("user-a", k=3) == [], "cleared LT user still has records")
        require(len(store.load_recent("user-b", k=3)) == 1, "LT clear leaked to other user")

    return True, "restore/isolation/clear-idempotent verified"


def run_checks() -> Iterable[tuple[str, bool, str]]:
    checks = [
        ("startup command surface", check_startup_command_surface),
        ("spinner cleanup on stream failure", check_spinner_cleanup_on_stream_failure),
        ("turn error fail-open + model reuse", check_turn_failure_recovery_and_model_reuse),
        ("stage2 ST restore/isolation", check_stage2_st_restore_isolation),
        ("stage3 LT restore/isolation/clear", check_stage3_lt_restore_isolation_clear),
    ]
    for name, fn in checks:
        try:
            ok, proof = fn()
        except Exception as exc:  # noqa: BLE001
            yield name, False, f"{type(exc).__name__}: {exc}"
            continue
        yield name, bool(ok), str(proof)


def main() -> int:
    failures = 0
    for name, ok, proof in run_checks():
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}")
        print(f"  proof: {proof}")
        if not ok:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
