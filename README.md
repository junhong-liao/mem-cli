# mem-cli

Minimal LangChain-based CLI conversational agent with:

- Runtime contracts and reset commands
- Short-term memory (thread-scoped sqlite checkpoints)
- Long-term memory (user-scoped JSONL records)
- Runtime hardening + scripted acceptance harness
- Reviewer ergonomics (`/session-show`, `/memory-show`)

## Runtime contracts

- Provider policy: Kimi/Moonshot only.
- Env loading: repo-local `.env` (or explicit `MEMCLI_ENV_PATH` override), no parent traversal.
- Identity defaults: `MEMCLI_USER_ID=default-user`, `MEMCLI_THREAD_ID=default-thread`.
- Commands: `/session-clear`, `/memory-clear`, `/session-show`, `/memory-show`, `/reset`, `/paste`, `/exit`.
- Clear commands and `/reset` are non-interactive and idempotent.
- Introspection commands are read-only, active-scope only, and bounded.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then set MOONSHOT_API_KEY in .env
python3 main.py
```

Make-based shortcut:

```bash
make setup
# edit .env and set MOONSHOT_API_KEY
make run
```

Required env:

- `MOONSHOT_API_KEY` (startup fails fast if missing)

Optional env:

- `MEMCLI_PROVIDER` (`moonshot`/`kimi`; other values are rejected)
- `MEMCLI_USER_ID`
- `MEMCLI_THREAD_ID`
- `MEMCLI_ENV_PATH`

## Acceptance harness

Run all acceptance checks (plus core regression checks):

```bash
./scripts/demo.sh
```

Direct harness invocation:

```bash
make harness
```

## Reviewer flow

Use this sequence for a deterministic reviewer run:

```bash
make check
make run
```

In CLI:

- Run `/session-show` to inspect active-thread short-term state only (bounded tail view).
- Run `/memory-show` to inspect active-user long-term memory only (bounded newest-first view).
- Run `/session-clear`, `/memory-clear`, or `/reset` as needed; all remain non-interactive/idempotent.
- Run `/exit` to leave CLI.

Then run:

```bash
./scripts/demo.sh
```

`scripts/demo.sh` is the single end-to-end reviewer entrypoint and calls `scripts/harness_checks.py`.

Fast verification (after setting `MOONSHOT_API_KEY`):

```bash
make demo
```

## Data layout

- ST checkpoints: `data/checkpoints.sqlite`
- LT memory: `data/memory/{sha256(user_id)}.jsonl` (record payload still stores raw `user_id`)
