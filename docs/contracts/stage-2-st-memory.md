# Stage 2 Contract: Short-Term Memory (ST)

Objective: Implement thread-scoped short-term memory persistence using LangGraph-style checkpointing semantics with file-backed sqlite so ST state survives process restarts by `thread_id`.

In scope:
- Add ST checkpoint persistence at `data/checkpoints.sqlite`.
- Persist ST state every user turn and restore automatically for active `thread_id`.
- Keep Stage 1 command surface and wire `/session-clear` to clear active-thread ST checkpoint state.
- Ensure `/session-clear` affects only active-thread ST state and remains idempotent/non-interactive.
- Add minimal runtime integration needed to load/save checkpoints (no UX redesign).
- Add any required dependency updates strictly needed for ST checkpoint implementation.

Out of scope:
- Long-term memory implementation (`data/memory/*.jsonl`, `memory_upsert`, LT retrieval).
- ST summarization/windowing/compaction.
- ST tool-call mediated updates or agent-driven memory tools.
- Provider, tracing, latency, and non-ST architecture changes.
- Harness/README expansion beyond short notes required to explain Stage 2 behavior.

Inputs:
- `docs/contracts/stage-1-runtime-commands.md`
- `docs/decisions.md`
- `docs/plan.md`
- `docs/takehome.md`
- Stage 1 baseline commit `71583f0`
- Runtime code under `main.py` and `cli_core/`

Outputs:
- ST checkpoint persistence implementation in code.
- Active-thread clear semantics for `/session-clear` backed by checkpoint deletion/reset.
- Command evidence for Stage 2 acceptance checks.
- Review packet with changed files, acceptance output, risks, and open questions.

Invariants:
- Kimi-only provider policy remains unchanged.
- Env loading remains repo-local/explicit override only.
- `/memory-clear` and LT behavior remain as Stage 1 placeholders (no LT implementation in Stage 2).
- `/session-clear`, `/memory-clear`, and `/reset` remain non-interactive and idempotent.
- No deferred/out-of-scope features from `docs/decisions.md` are introduced.

Acceptance checks:
- `python3 -m py_compile $(rg --files -g '*.py')`
- `python3 main.py` starts and still shows `/session-clear`, `/memory-clear`, `/reset`.
- `data/checkpoints.sqlite` is created after at least one user turn.
- Same `MEMCLI_THREAD_ID` restores ST across a fresh process start (evidence must show prior-turn context is loaded from checkpoint storage, not only same-process history).
- Different `MEMCLI_THREAD_ID` does not load prior ST from another thread.
- `/session-clear` clears only active-thread ST: cleared thread starts empty while another thread retains prior ST.
- `/session-clear` remains idempotent when run repeatedly on already-cleared thread state.

Failure semantics:
- If checkpoint load/read fails, log actionable warning and continue with empty ST for that thread.
- If checkpoint write fails for a turn, return an actionable error for that turn and keep CLI process alive.
- If dependency/import errors are encountered, fail fast with clear install guidance.
- If requirements are ambiguous, stop and ask focused blocking questions before changing code.

Rollback:
- Revert only Stage 2 commit(s) and restore Stage 1 baseline behavior.
- Keep contract and review artifacts intact for auditability.

Decision ID:
- `DEC-02-05-STAGE2-ST-MEMORY`
