# mem-cli

Minimal LangChain-based CLI conversational agent with:

- Stage 1 runtime contracts and reset commands
- Stage 2 short-term memory (thread-scoped sqlite checkpoints)
- Stage 3 long-term memory (user-scoped JSONL records)
- Stage 4 runtime hardening + scripted acceptance harness

## Runtime contracts

- Provider policy: Kimi/Moonshot only.
- Env loading: repo-local `.env` (or explicit `MEMCLI_ENV_PATH` override), no parent traversal.
- Identity defaults: `MEMCLI_USER_ID=default-user`, `MEMCLI_THREAD_ID=default-thread`.
- Commands: `/session-clear`, `/memory-clear`, `/reset`, `/paste`, `/exit`.
- Clear commands and `/reset` are non-interactive and idempotent.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Required env:

- `MOONSHOT_API_KEY` (startup fails fast if missing)

Optional env:

- `MEMCLI_PROVIDER` (`moonshot`/`kimi`; other values are rejected)
- `MEMCLI_USER_ID`
- `MEMCLI_THREAD_ID`
- `MEMCLI_ENV_PATH`

## Stage 4 acceptance harness

Run all Stage 4 acceptance checks (plus Stage 1-3 regression checks):

```bash
./scripts/run_stage4_acceptance.sh
```

Direct harness invocation:

```bash
python3 scripts/stage4_acceptance.py
```

## Data layout

- ST checkpoints: `data/checkpoints.sqlite`
- LT memory: `data/memory/{user_id}.jsonl`
