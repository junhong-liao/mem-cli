# Stage 5 Contract: Reviewer Ergonomics

Objective: Improve reviewer usability and inspection clarity (without changing memory architecture) so reviewers can quickly understand and validate behavior.

In scope:
- Add reviewer-facing introspection commands `/session-show` and `/memory-show`.
- Keep introspection scoped to active `thread_id` and active `user_id` only.
- Ensure introspection output is bounded and deterministic.
- Tighten README reviewer flow (quickstart, command semantics, verification path).
- Keep script naming/references reviewer-friendly (`scripts/demo.sh`, `scripts/harness_checks.py`).
- Include seeded scripted conversation demo checks in `scripts/demo.sh` as final reviewer verification.

Out of scope:
- New memory retrieval/ranking features or LT schema changes.
- Provider/env contract changes.
- Runtime architecture refactors unrelated to reviewer ergonomics.

Inputs:
- `docs/decisions.md`
- `docs/plan.md`
- `docs/takehome.md`
- `README.md`
- `main.py`
- `cli_core/runtime.py`
- `cli_core/lt_memory.py`
- `cli_core/checkpoints.py`

Outputs:
- Command wiring and handlers for `/session-show` and `/memory-show`.
- Updated docs reflecting reviewer workflow and command behavior.
- Review packet with changed files, acceptance evidence, risks, and open questions.

Invariants:
- Stage 1 env/identity/provider contracts remain unchanged.
- Stage 2 ST checkpoint behavior remains intact.
- Stage 3 LT persistence/retrieval/clear behavior remains intact.
- Stage 4 runtime hardening behavior remains intact.
- All clear/reset commands remain non-interactive and idempotent.

Acceptance checks:
- `python3 -m py_compile $(rg --files -g '*.py')`
- `python3 main.py` startup still shows `/session-clear`, `/memory-clear`, `/reset`, `/paste`, `/exit`.
- `/session-show` displays active-thread session messages only, bounded.
- `/memory-show` displays active-user LT memories only, bounded.
- `/session-show` and `/memory-show` on empty state return deterministic "empty" output, no errors.
- Existing Stage 2 ST checks still pass.
- Existing Stage 3 LT checks still pass.
- Existing Stage 4 harness checks still pass via `./scripts/demo.sh`.

Failure semantics:
- Introspection command failures return bounded warning text and continue CLI loop.
- If expected storage artifacts are missing, commands report empty state (not failure).
- If contract ambiguity appears, pause and ask focused blocking questions.

Rollback:
- Revert only Stage 5 code/doc changes; keep Stage 1-4 unchanged.

Decision ID:
- `DEC-02-05-STAGE5-REVIEWER-ERGONOMICS`
