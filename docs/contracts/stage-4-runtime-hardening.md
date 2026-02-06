# Stage 4 Contract: Runtime Hardening and Harness

Objective: Harden runtime reliability and reviewability by fixing known runtime lifecycle issues, adding minimal verification harness coverage, and finalizing reviewer-facing docs without changing Stage 1-3 feature contracts.

In scope:
- Runtime model lifecycle hardening: build/bind model once per CLI session and reuse across turns.
- Stream indicator hardening: guarantee spinner/thread cleanup with `try/finally` on all stream paths (success/failure).
- Add explicit turn-level error messaging behavior for stream failures that keeps process alive.
- Add minimal scripted harness checks for Stage 1-3 contracts (startup/env, ST restore, LT restore/clear).
- Final docs polish for reviewer runbook and known deferrals.

Out of scope:
- New memory features beyond Stage 3 scope.
- Provider expansion beyond Kimi-only.
- Architecture refactors unrelated to runtime lifecycle/cleanup/harness.
- Performance benchmarking suite beyond targeted checks required for acceptance.

Inputs:
- `docs/contracts/stage-3-lt-memory.md`
- `docs/decisions.md`
- `docs/plan.md`
- `docs/takehome.md`
- Runtime code under `main.py` and `cli_core/`

Outputs:
- Runtime hardening code changes for model reuse and robust indicator cleanup.
- Scripted verification artifacts/commands for reviewer confidence.
- Updated docs describing run flow, reset semantics, and deferred items.
- Review packet with changed files, acceptance output, risks, and open questions.

Invariants:
- Stage 1 env/identity/command contracts remain unchanged.
- Stage 2 ST checkpoint behavior remains intact.
- Stage 3 LT memory behavior remains intact.
- Commands remain non-interactive and idempotent.
- Kimi-only provider policy remains enforced.

Acceptance checks:
- `python3 -m py_compile $(rg --files -g '*.py')`
- Startup command surface remains `/session-clear`, `/memory-clear`, `/reset`, `/paste`, `/exit`.
- Forced stream failure path emits actionable error and CLI remains usable for subsequent turn.
- Thinking indicator cleanup always runs (no stuck spinner/thread on stream error).
- Per-session model build/bind is reused across multiple turns (no per-turn rebuild in steady state).
- Existing Stage 2 ST restore/isolation checks still pass.
- Existing Stage 3 LT restore/isolation/clear checks still pass.

Failure semantics:
- Runtime stream/tool failures should return actionable, bounded errors and continue loop where safe.
- If a hard startup invariant fails, fail fast with clear guidance.
- If harness/doc requirements are ambiguous, stop and ask focused blocking questions before edits.

Rollback:
- Revert only Stage 4 commit(s); keep Stage 1-3 behavior intact.
- Keep contract and review artifacts for auditability.

Decision ID:
- `DEC-02-05-STAGE4-RUNTIME-HARDENING-HARNESS`
