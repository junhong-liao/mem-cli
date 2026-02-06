#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="python3"
if [[ -x "$ROOT/.venv/bin/python3" ]]; then
  PYTHON_BIN="$ROOT/.venv/bin/python3"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "[1/2] Compile check"
"$PYTHON_BIN" -m py_compile $(rg --files -g '*.py')

echo "[2/2] Stage 4 acceptance harness"
"$PYTHON_BIN" scripts/stage4_acceptance.py
