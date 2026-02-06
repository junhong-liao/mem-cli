#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ARTIFACTS_DIR="$ROOT/artifacts"
TRANSCRIPT_FILE="$ARTIFACTS_DIR/demo_transcript.txt"

PYTHON_BIN="python3"
if [[ -x "$ROOT/.venv/bin/python3" ]]; then
  PYTHON_BIN="$ROOT/.venv/bin/python3"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

if [[ -z "${MOONSHOT_API_KEY:-}" && -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "$ROOT/.env"
  set +a
fi

if [[ -z "${MOONSHOT_API_KEY:-}" ]]; then
  echo "FAIL: MOONSHOT_API_KEY is required. Set it in env or $ROOT/.env"
  exit 1
fi

RUN_ID="$(date +%s)"
USER_A="demo-user-a-$RUN_ID"
USER_B="demo-user-b-$RUN_ID"
THREAD_A="demo-thread-a-$RUN_ID"
THREAD_B="demo-thread-b-$RUN_ID"
ST_TOKEN="ST-TOKEN-$RUN_ID"
LT_FACT="Favorite database is PostgreSQL."
mkdir -p "$ARTIFACTS_DIR"

cat >"$TRANSCRIPT_FILE" <<EOF
demo.sh transcript
run_id=$RUN_ID
user_a=$USER_A
user_b=$USER_B
thread_a=$THREAD_A
thread_b=$THREAD_B
st_token=$ST_TOKEN
lt_fact=$LT_FACT
EOF

assert_contains() {
  local haystack="$1"
  local needle="$2"
  local label="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    echo "[PASS] $label"
  else
    echo "[FAIL] $label"
    echo "Expected to find: $needle"
    exit 1
  fi
}

assert_not_contains() {
  local haystack="$1"
  local needle="$2"
  local label="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    echo "[FAIL] $label"
    echo "Unexpectedly found: $needle"
    exit 1
  else
    echo "[PASS] $label"
  fi
}

assert_no_turn_error() {
  local haystack="$1"
  local label="$2"
  assert_not_contains "$haystack" "Turn error: model invocation failed." "$label"
}

run_cli() {
  local user_id="$1"
  local thread_id="$2"
  local input_text="$3"
  MEMCLI_USER_ID="$user_id" MEMCLI_THREAD_ID="$thread_id" "$PYTHON_BIN" main.py <<<"$input_text"
}

append_transcript_block() {
  local title="$1"
  local content="$2"
  {
    echo ""
    echo "===== $title ====="
    printf '%s\n' "$content"
  } >>"$TRANSCRIPT_FILE"
}

echo "[1/4] Compile check"
"$PYTHON_BIN" -m py_compile $(rg --files -g '*.py')

echo "[2/4] Seeded conversation checks (ST vs LT)"

out_startup="$(run_cli "$USER_A" "$THREAD_A" $'/exit')"
append_transcript_block "startup" "$out_startup"
assert_contains "$out_startup" "commands: /session-clear /memory-clear /reset /paste /exit" "startup command surface"

out_st_seed="$(run_cli "$USER_A" "$THREAD_A" $'For this session only, remember this token exactly: '"$ST_TOKEN"$'.\nReply only with: ACK.\n/exit')"
append_transcript_block "st_seed" "$out_st_seed"
assert_no_turn_error "$out_st_seed" "seed ST turn succeeds"

out_st_verify="$(run_cli "$USER_A" "$THREAD_A" $'What token did I ask you to remember earlier in this thread? Reply with token only.\n/exit')"
append_transcript_block "st_verify_same_thread" "$out_st_verify"
assert_no_turn_error "$out_st_verify" "verify ST turn succeeds"
assert_contains "$out_st_verify" "$ST_TOKEN" "ST token persisted in active thread"

out_st_iso="$(run_cli "$USER_A" "$THREAD_B" $'/session-show\n/exit')"
append_transcript_block "st_isolation_other_thread" "$out_st_iso"
assert_contains "$out_st_iso" "Session empty for active thread (thread_id=$THREAD_B)." "ST isolation across threads"
assert_not_contains "$out_st_iso" "$ST_TOKEN" "No ST token leakage to another thread"

out_lt_seed="$(run_cli "$USER_A" "$THREAD_A" $'Call tool memory_upsert exactly once with content: '"$LT_FACT"$' Then reply with STORED.\n/memory-show\n/exit')"
if [[ "$out_lt_seed" != *"$LT_FACT"* ]]; then
  out_lt_seed="$(run_cli "$USER_A" "$THREAD_A" $'Use memory_upsert now. Save this exact content: '"$LT_FACT"$'. Then reply STORED.\n/memory-show\n/exit')"
fi
append_transcript_block "lt_seed_user_a" "$out_lt_seed"
assert_no_turn_error "$out_lt_seed" "seed LT turn succeeds"

out_lt_cross_thread="$(run_cli "$USER_A" "$THREAD_B" $'/memory-show\n/exit')"
append_transcript_block "lt_verify_user_a_other_thread" "$out_lt_cross_thread"
assert_no_turn_error "$out_lt_cross_thread" "verify LT cross-thread turn succeeds"
assert_contains "$out_lt_cross_thread" "$LT_FACT" "LT memory available across threads for same user"

out_lt_user_iso="$(run_cli "$USER_B" "$THREAD_A" $'/memory-show\n/exit')"
append_transcript_block "lt_isolation_user_b" "$out_lt_user_iso"
assert_contains "$out_lt_user_iso" "Memory empty for active user (user_id=$USER_B)." "LT user isolation"

out_mem_clear="$(run_cli "$USER_A" "$THREAD_B" $'/memory-clear\n/memory-clear\n/memory-show\n/exit')"
append_transcript_block "memory_clear_user_a" "$out_mem_clear"
assert_contains "$out_mem_clear" "Memory cleared for active user." "memory-clear first invocation"
assert_contains "$out_mem_clear" "Memory already clear for active user (no persisted memory to remove)." "memory-clear idempotency"
assert_contains "$out_mem_clear" "Memory empty for active user (user_id=$USER_A)." "memory-clear result is empty memory"

echo "[3/4] Runtime hardening + regression checks"
harness_out="$("$PYTHON_BIN" scripts/harness_checks.py 2>&1)"
echo "$harness_out"
append_transcript_block "runtime_hardening_harness" "$harness_out"

echo "[4/4] Demo summary"
echo "PASS: seeded ST/LT scenario and harness checks complete"
echo "user_a=$USER_A thread_a=$THREAD_A thread_b=$THREAD_B"
echo "transcript=$TRANSCRIPT_FILE"
