# Mem CLI Decisions

This file is the source of truth for locked architecture decisions for this repo.
Update this file before implementation when scope or contracts change.

## Locked Decisions

### Scope and Runtime Core

- Date: 02-05
- Decision: Project boundary
- Status: Locked
- Details: `mem-cli` is a standalone project and must not depend on original TUI code or repo structure.

- Date: 02-05
- Decision: Core runtime direction
- Status: Locked
- Details: Keep a general CLI agent core using LangChain tooling, LangSmith tracing, and latency logging.

### Provider and Environment

- Date: 02-05
- Decision: Provider scope
- Status: Locked
- Details: `Kimi-only` provider policy; keep Moonshot adapter as the only supported provider in this repo.

- Date: 02-05
- Decision: Environment loading scope
- Status: Locked
- Details: Load environment variables only from this repo's `.env` (`/Users/junho/agents/mem-cli/.env`) or an explicit override path; do not traverse parent directories.

### Identity and Session Boundaries

- Date: 02-05
- Decision: Identity defaults for reviewer runs
- Status: Locked
- Details: Default `user_id=default-user` and `thread_id=default-thread`; allow overrides via `MEMCLI_USER_ID` and `MEMCLI_THREAD_ID`. Rationale: deterministic out-of-the-box resume behavior for both ST and LT memory in manual reviewer runs, while still allowing isolation tests by overriding either handle.

### Short-Term Memory (ST)

- Date: 02-05
- Decision: Short-term memory strategy
- Status: Locked
- Details: Use LangGraph thread-scoped checkpoints with file-backed persistence via local sqlite (`data/checkpoints.sqlite`); write on every turn and restore by `thread_id` automatically; no ST tool-call updates and no summarization/windowing in this repo.

### Long-Term Memory (LT)

- Date: 02-05
- Decision: Long-term memory strategy
- Status: Locked
- Details: Use file-based cross-thread persistence (JSONL under `data/`) following LangChain/LangGraph store contracts; no SQLite for long-term memory in this repo.

- Date: 02-05
- Decision: Long-term memory file contract
- Status: Locked
- Details: Store LT records in `data/memory/{user_id}.jsonl` with one JSON object per line. Required fields in v1: `id`, `user_id`, `content`, `kind`, `created_at`, and `updated_at`. Optional fields in v1: `confidence` and `source_turn_id`.

- Date: 02-05
- Decision: LT missing file behavior
- Status: Locked
- Details: If `data/memory/{user_id}.jsonl` does not exist, reads treat it as empty memory; create the file on first successful LT write.

- Date: 02-05
- Decision: LT corrupt file handling
- Status: Locked
- Details: If LT JSONL is unreadable/corrupt, log a warning and treat LT as empty for that run; keep the file untouched in v1 to minimize implementation risk.

- Date: 02-05
- Decision: Long-term memory write policy
- Status: Locked
- Details: LT writes are model-mediated via a single `memory_upsert` tool (no deterministic extractor). Guardrails: at most one LT write per user turn; store only durable user facts/preferences/stable constraints; skip transient requests and one-off chatter; include `source_turn_id` when available; if uncertain, do not store.

- Date: 02-05
- Decision: Long-term upsert and clear scope
- Status: Locked
- Details: `memory_upsert` is append-only in v1 (no dedupe); `/memory-clear` deletes LT records only for the active `user_id`; `/reset` applies both session and active-user LT clear.

- Date: 02-05
- Decision: Long-term memory read policy
- Status: Locked
- Details: On every user turn, retrieve LT memory before response generation for the active `user_id`; inject the top `k=3` results into a fixed prompt block (`Known memory`) used as optional context, not absolute truth.

- Date: 02-05
- Decision: Long-term retrieval method and bounds
- Status: Locked
- Details: Use recency-first retrieval in v1: read active-user LT records and return the latest `k=3`. If needed, lightweight lexical scoring may be added, but no per-turn model-based ranking is required in v1.

### Commands and Reset Behavior

- Date: 02-05
- Decision: Reset command contract
- Status: Locked
- Details: `/session-clear` clears session/short-term state, `/memory-clear` clears long-term persisted memory, and `/reset` performs full clear (both).

- Date: 02-05
- Decision: Command confirmation UX
- Status: Locked
- Details: No interactive confirmation prompts in v1; `/session-clear`, `/memory-clear`, and `/reset` execute immediately.

- Date: 02-05
- Decision: Clear command idempotency and delete semantics
- Status: Locked
- Details: Clear commands are idempotent: if target state is already empty or missing, return success with an informational message. `/session-clear` removes active-thread ST checkpoint state; `/memory-clear` clears only active-user LT state; `/reset` applies both.

### Reliability and Validation

- Date: 02-05
- Decision: Failure behavior policy
- Status: Locked
- Details: Missing `MOONSHOT_API_KEY` fails fast with actionable startup error. LT retrieval/write failures are fail-open (log warning and continue chat without LT context). Core model invocation failures return an error message for the turn and keep the CLI session alive.

- Date: 02-05
- Decision: Harness acceptance contract
- Status: Locked
- Details: Include a scripted harness with three demos and pass criteria: (1) ST continuity in same `thread_id` (pronoun/follow-up resolved), (2) LT recall across new `thread_id` for same `user_id`, (3) LT isolation for different `user_id` (no cross-user recall).

## Open Decisions

None.

## Tradeoffs (Locked)

- Decision: Kimi-only provider scope.
- Chosen option: Moonshot/Kimi only in this repo.
- Alternatives considered: multi-provider adapter matrix.
- Why now: minimizes config drift and implementation/testing surface for reviewer runs.
- Revisit trigger: requirement to compare providers or support non-Kimi environments.

- Decision: ST memory via LangGraph sqlite checkpoints.
- Chosen option: file-backed checkpoints in `data/checkpoints.sqlite` with automatic per-turn writes.
- Alternatives considered: in-memory-only checkpoints, custom file checkpoint layer.
- Why now: resume behavior works across process restarts with low operational overhead.
- Revisit trigger: need for distributed concurrency or remote/shared checkpointing.

- Decision: LT memory stored as JSONL files.
- Chosen option: file-based store in `data/memory/{user_id}.jsonl`.
- Alternatives considered: SQLite-backed LT store, hosted/vector DB backends.
- Why now: simple local inspection, fast implementation, no extra service dependencies.
- Revisit trigger: memory volume/performance limits or multi-process consistency needs.

- Decision: LT writes are model-mediated via `memory_upsert`.
- Chosen option: tool-based writes with guardrails (durable facts only, max 1 write per turn).
- Alternatives considered: deterministic extraction rules.
- Why now: better semantic capture of preferences/constraints than brittle fixed parsers.
- Revisit trigger: high false-positive memory writes or auditability requirements.

- Decision: LT retrieval is recency-first top-3 in v1.
- Chosen option: latest `k=3` LT records for active `user_id`.
- Alternatives considered: Kimi-assisted ranking each turn, vector embedding retrieval.
- Why now: lowest implementation risk while still demonstrating cross-thread LT recall for the assignment.
- Revisit trigger: recall quality gaps in demos or requirement for semantic retrieval quality.

- Decision: fixed identity defaults for reviewer runs.
- Chosen option: `default-user` and `default-thread` with env overrides.
- Alternatives considered: random IDs per process start.
- Why now: deterministic out-of-box behavior makes ST/LT demo reproducible.
- Revisit trigger: requirement for strict per-run isolation by default.

## Deferred (Out of Scope for v1)

- LT deduplication and merge strategy (append-only writes in v1).
- Kimi-assisted semantic ranking on every turn for LT retrieval.
- LT corrupt-file quarantine/rename flow (`*.corrupt.<timestamp>`).
- Strict enrichment requirements for LT metadata (`confidence`, `source_turn_id` mandatory).
- Vector DB / embedding-based retrieval backend.
- Multi-namespace LT beyond `user_id` scoping.
- Interactive confirmations (`--yes` style flow) for destructive commands.
- Advanced retention and compaction policies for LT files.
- Any non-essential hardening not explicitly required and not needed for reliable ST/LT demonstration.
