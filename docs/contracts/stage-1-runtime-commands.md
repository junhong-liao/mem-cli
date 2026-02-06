# Stage 1 Contract: Runtime Contracts and Commands

Objective: Implement Stage 1 runtime contracts so the CLI boots with deterministic Kimi-only behavior and correct reset commands.

In scope:
- Repo-local env loading only (`/Users/junho/agents/mem-cli/.env` or explicit override path).
- Kimi-only provider enforcement and startup validation for `MOONSHOT_API_KEY`.
- Identity defaults with env overrides (`default-user` / `default-thread` and `MEMCLI_USER_ID` / `MEMCLI_THREAD_ID`).
- Command contract implementation for `/session-clear`, `/memory-clear`, and `/reset`.
- Idempotent, non-interactive clear command behavior.
- Minimal docs updates required to explain Stage 1 behavior if code paths changed.

Out of scope:
- ST checkpoint persistence implementation details beyond command hooks needed for Stage 1 wiring.
- LT storage format/tooling implementation beyond command hooks needed for Stage 1 wiring.
- Harness automation and Stage 2/3/4 tasks.
- Any provider support beyond Moonshot/Kimi.

Inputs:
- `docs/decisions.md`
- `docs/plan.md`
- `docs/takehome.md`
- Existing runtime files under `main.py` and `cli_core/`

Outputs:
- Updated runtime/env/provider/command wiring in code.
- Command behavior evidence from local runs.
- Short reviewer-friendly change report with changed files, checks, risks, and open questions.

Invariants:
- Kimi-only provider policy remains enforced.
- Env loading does not traverse parent directories.
- Clear commands are non-interactive and idempotent.
- No out-of-scope deferred features are introduced.
- Existing LangSmith tracing, LangChain tooling path, and latency logging are not removed.

Acceptance checks:
- `python3 -m py_compile $(rg --files -g '*.py')`
- `python3 main.py` starts and shows command surface including `/session-clear`, `/memory-clear`, `/reset`.
- Missing `MOONSHOT_API_KEY` produces actionable fail-fast startup error.
- Default identity is `default-user` and `default-thread` when env overrides are absent.
- `MEMCLI_USER_ID` / `MEMCLI_THREAD_ID` overrides are honored.
- Re-running each clear command from already-cleared state returns success/info (idempotent behavior).

Failure semantics:
- On startup contract violations (missing key, unsupported provider), fail fast with actionable error.
- On command clear calls when target state is absent, return success/info without exception.
- If implementation blocks on ambiguity, stop and ask focused blocking questions before proceeding.

Rollback:
- Revert Stage 1 commit(s) only; do not touch unrelated files.
- Keep docs contract file and report evidence even if rollback is needed.

Decision ID:
- `DEC-02-05-STAGE1-RUNTIME-COMMANDS`
