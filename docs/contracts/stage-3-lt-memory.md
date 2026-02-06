# Stage 3 Contract: Long-Term Memory (LT)

Objective: Implement user-scoped long-term memory persistence and retrieval using JSONL files so durable facts survive process restarts and are available to the agent across sessions.

In scope:
- Add LT memory storage at `data/memory/{user_id}.jsonl`.
- Implement a `memory_upsert` tool for model-mediated LT writes/updates.
- Load LT records for active `user_id` on each turn and inject a bounded LT context into prompt construction.
- Use v1 retrieval policy: recency-first top `k=3` LT records.
- Wire `/memory-clear` to clear only active-user LT records.
- Keep `/reset` behavior as full clear (`/session-clear` + `/memory-clear`) and idempotent/non-interactive.
- Add minimal runtime/tool wiring needed for Stage 3 only.

Out of scope:
- Vector database, embeddings, or semantic search infrastructure.
- Deterministic fact extraction pipelines outside model-mediated `memory_upsert`.
- LT summarization/compaction, confidence scoring, or rich ranking pipelines.
- Corrupt-file quarantine/rename flow (`*.corrupt.<timestamp>`); defer to later stage.
- Multi-provider, auth, remote memory backends, or non-memory architecture refactors.
- Stage 4 harness expansion beyond checks required to prove Stage 3 behavior.

Inputs:
- `docs/contracts/stage-2-st-memory.md`
- `docs/decisions.md`
- `docs/plan.md`
- `docs/takehome.md`
- Stage 2 baseline commit `fb901d1`
- Runtime/tooling code under `main.py` and `cli_core/`

Outputs:
- LT memory implementation in code (JSONL store, model-mediated upsert tool, prompt injection, clear semantics).
- Command evidence for Stage 3 acceptance checks.
- Review packet with changed files, acceptance output, risks, and open questions.

Invariants:
- Kimi-only provider policy remains unchanged.
- Env loading remains repo-local/explicit override only.
- ST checkpoint behavior from Stage 2 remains intact.
- `/session-clear`, `/memory-clear`, and `/reset` remain non-interactive and idempotent.
- LT store is file-based JSONL in repo data dir; no DB/vector infra introduced for LT.
- Deferred items in `docs/decisions.md` remain deferred unless contract is explicitly updated.

Acceptance checks:
- `python3 -m py_compile $(rg --files -g '*.py')`
- `python3 main.py` starts and still shows `/session-clear`, `/memory-clear`, `/reset`.
- First LT write creates `data/memory/{user_id}.jsonl` with valid JSONL records.
- Same `MEMCLI_USER_ID` across fresh process restart restores LT influence (assistant can use previously stored durable fact).
- Different `MEMCLI_USER_ID` does not load another user’s LT records.
- LT retrieval is bounded to top `k=3` records (recency-first) for prompt context.
- `/memory-clear` clears only active-user LT data and is idempotent on repeated runs.
- `/reset` clears active-thread ST and active-user LT, both idempotently.

Failure semantics:
- Missing LT file is treated as empty memory state.
- Malformed LT JSONL line is skipped with warning; process continues.
- LT write failure returns actionable turn warning/error while keeping CLI alive.
- If contract requirements are ambiguous, stop and ask focused blocking questions before code changes.

Rollback:
- Revert only Stage 3 commit(s) and restore Stage 2 baseline behavior.
- Keep contract and review artifacts intact for auditability.

Decision ID:
- `DEC-02-05-STAGE3-LT-MEMORY`
