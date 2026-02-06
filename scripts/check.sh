#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="python3"
if [[ -x "$ROOT/.venv/bin/python3" ]]; then
  PYTHON_BIN="$ROOT/.venv/bin/python3"
fi

if command -v rg >/dev/null 2>&1; then
  mapfile -t PY_FILES < <(rg --files -g '*.py')
else
  mapfile -t PY_FILES < <(find . -type f -name '*.py' -not -path './.venv/*' -not -path './.git/*' | sed 's|^\./||')
fi

if [[ "${#PY_FILES[@]}" -eq 0 ]]; then
  echo "No Python files found."
  exit 0
fi

"$PYTHON_BIN" -m py_compile "${PY_FILES[@]}"
echo "PASS: py_compile (${#PY_FILES[@]} files)"
