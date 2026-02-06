# Mem CLI Implementation Plan

This plan is derived from `docs/decisions.md` and is execution-only.

## Stage 1: Runtime Contracts and Commands

- Enforce repo-local env loading only (`.env` in this repo or explicit override).
- Enforce Kimi-only provider path and clear startup error for missing `MOONSHOT_API_KEY`.
- Wire identity defaults (`default-user`, `default-thread`) with env overrides.
- Implement command contract: `/session-clear`, `/memory-clear`, `/reset`.
- Ensure clear commands are idempotent and non-interactive.
- Exit criteria: CLI starts with deterministic identity defaults and command semantics match decisions.

## Stage 2: Short-Term Memory (ST)

- Add LangGraph thread-scoped checkpoint persistence at `data/checkpoints.sqlite`.
- Persist ST every turn and restore by active `thread_id`.
- Keep ST behavior minimal: no summarization/windowing and no ST tool-call updates.
- Verify `/session-clear` only affects active-thread ST state.
- Exit criteria: same-thread follow-up works across turns and can be cleared independently.

## Stage 3: Long-Term Memory (LT)

- Implement file-backed LT store at `data/memory/{user_id}.jsonl`.
- Enforce v1 required fields: `id`, `user_id`, `content`, `kind`, `created_at`, `updated_at`.
- Allow optional fields: `confidence`, `source_turn_id`.
- Add model-mediated `memory_upsert` tool with locked write guardrails.
- Add v1 recency-first LT retrieval (`k=3`) for active `user_id`.
- Implement missing/corrupt LT file behavior per locked decisions.
- Exit criteria: LT recall works across new thread for same user and stays isolated across users.

## Stage 4: Reliability, Harness, and Docs

- Enforce fail-open LT errors and fail-fast startup behavior for missing API key.
- Add scripted harness covering ST continuity, LT cross-thread recall, and LT user isolation.
- Update README with run steps, env contract, and memory behavior explanation.
- Add concise tradeoff write-up aligned to `docs/decisions.md`.
- Exit criteria: harness scenarios pass and docs explain behavior and scope boundaries.

## Stage 5: Reviewer Ergonomics

- Add read-only introspection commands scoped to active identity: `/memory-show` and `/session-show`.
- Keep introspection bounded and deterministic (no global memory dump across users).
- Add a no-fluff reviewer runbook with quickstart and exact verification steps.
- Add a single scripted reviewer demo command for reproducible ST/LT behavior checks.
- Exit criteria: reviewer can verify ST/LT behavior quickly without ad-hoc probing.

## Validation Gates (Each Stage)

- `python3 -m py_compile $(rg --files -g '*.py')`
- `python3 main.py` roundtrip works in local venv.
- Command semantics match locked contracts in `docs/decisions.md`.
- No out-of-scope features from `Deferred (Out of Scope for v1)` are introduced.
