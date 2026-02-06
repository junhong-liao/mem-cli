```yaml
review_packet:
  change_id: "DEC-02-05-STAGE3-LT-MEMORY"
  objective: "Implement Stage 3 LT memory: JSONL store, model-mediated memory_upsert, per-turn LT retrieval injection (k=3 recency-first), and active-user /memory-clear with /reset semantics preserved."
  rationale: "Deliver durable cross-session memory while keeping Stage 2 ST behavior and locked provider/env contracts unchanged."
  contract_ref:
    decision_id: "DEC-02-05-STAGE3-LT-MEMORY"
    stage_objective: "User-scoped LT persistence/retrieval via JSONL with idempotent clear/reset semantics."
  files_changed:
    - path: "main.py"
      lines_touched: [8, 21, 28, 32, 78, 141, 164, 242, 258]
    - path: "cli_core/runtime.py"
      lines_touched: [112, 117, 122, 126]
    - path: "cli_core/lt_memory.py"
      lines_touched: [1, 14, 31, 69, 104]
  behavioral_changes:
    - "Added LT JSONL store at data/memory/{user_id}.jsonl with required fields (id,user_id,content,kind,created_at,updated_at) and optional confidence/source_turn_id."
    - "Added model tool memory_upsert (append-only v1) scoped to active user_id."
    - "Added per-turn LT retrieval before prompt build; injects recency-first top k=3 into Known memory block."
    - "Enforced max one memory_upsert write per turn in runtime tool wrapper."
    - "Updated /memory-clear to clear only active-user LT file, idempotently."
    - "Kept /reset as full clear (session ST + active-user LT), idempotent."
    - "Malformed LT JSONL lines are skipped with warning; missing LT file treated as empty."
  risks:
    level: "medium"
    notes: "memory_upsert is model-mediated; write frequency/quality depends on model tool-use behavior. No dedupe/compaction in v1 by contract."
  tests:
    commands:
      - "source .venv/bin/activate && python3 -m py_compile $(rg --files -g '*.py')"
      - "source .venv/bin/activate && printf '/exit\\n' | python3 main.py"
      - "source .venv/bin/activate && scenario checks for LT create/recall/isolation/k-bound/clear/reset"
      - "git status --short"
      - "git diff -- main.py cli_core/runtime.py && git diff --no-index /dev/null cli_core/lt_memory.py"
    results: "pass"
  acceptance_evidence:
    - check: "python3 -m py_compile $(rg --files -g '*.py')"
      command: "source .venv/bin/activate && python3 -m py_compile $(rg --files -g '*.py')"
      result: "pass"
      proof: "Exit code 0; no output."
    - check: "CLI starts and shows /session-clear, /memory-clear, /reset"
      command: "source .venv/bin/activate && printf '/exit\\n' | python3 main.py"
      result: "pass"
      proof: "Startup line includes commands: /session-clear /memory-clear /reset /paste /exit"
    - check: "First LT write creates data/memory/{user_id}.jsonl with valid JSONL"
      command: "MEMCLI_USER_ID=stage3-user-alpha MEMCLI_THREAD_ID=stage3-thread-one python3 main.py ..."
      result: "pass"
      proof: "memory_upsert saved record id; file exists; required fields present."
    - check: "Same MEMCLI_USER_ID across fresh restart shows LT influence"
      command: "MEMCLI_USER_ID=stage3-user-alpha MEMCLI_THREAD_ID=stage3-thread-two python3 main.py ..."
      result: "pass"
      proof: "Fresh thread restored_messages=0 and assistant recalls stored preference."
    - check: "Different MEMCLI_USER_ID isolation"
      command: "MEMCLI_USER_ID=stage3-user-beta MEMCLI_THREAD_ID=stage3-thread-three python3 main.py ..."
      result: "pass"
      proof: "No cross-user LT leakage observed."
    - check: "LT retrieval bounded to top k=3 recency-first"
      command: "python3 - <<'PY' ... JsonlLongTermMemoryStore load_recent probe ... PY"
      result: "pass"
      proof: "Retrieved 3 records with expected recency ordering."
    - check: "/memory-clear active-user only + idempotent"
      command: "Run /memory-clear twice for alpha; verify alpha cleared while beta remains"
      result: "pass"
      proof: "First clear succeeds; second reports already clear; other user file unchanged."
    - check: "/reset clears active-thread ST and active-user LT, idempotently"
      command: "Create ST+LT state, run /reset twice, verify checkpoint rows and LT file state"
      result: "pass"
      proof: "After reset: ST row removed and LT file removed; second reset remains informational/idempotent."
    - check: "max one write per turn enforcement"
      command: "Prompt model to call memory_upsert twice in one turn"
      result: "pass"
      proof: "Second write skipped with explicit message; only one LT record written."
  manual_checks:
    - step: "Run report gate"
      expected: "PASS verify-report"
  diagnostics_added:
    - name: "none"
      fields: []
  rollback:
    - "git restore -- main.py cli_core/runtime.py"
    - "git clean -f cli_core/lt_memory.py"
```

```json
{
  "collected_at": "2026-02-06T02:38:08.408190Z",
  "git_root": "/Users/junho/agents/mem-cli",
  "branch": "main",
  "head_sha": "fb901d1580220cc5930506bb1d8f82f383ddeefb",
  "recent_commits": "fb901d1 feat: implement stage 2 short-term checkpoint persistence\n71583f0 feat: implement stage 1 runtime contracts and commands\n3eda318 chore: finalize baseline cli labels and trace wiring\n201d7d6 docs: lock architecture decisions and staged implementation plan\nfd1767d chore: bootstrap cli core",
  "status_porcelain": "M cli_core/runtime.py\n M main.py\n?? cli_core/lt_memory.py\n?? docs/contracts/stage-3-lt-memory.md\n?? docs/contracts/stage-4-runtime-hardening.md",
  "range_used": null,
  "diff_stat": "cli_core/runtime.py |  17 +++++++-\n main.py             | 115 +++++++++++++++++++++++++++++++++++++++++++++++++---\n 2 files changed, 125 insertions(+), 7 deletions(-)",
  "diff": "diff --git a/cli_core/runtime.py b/cli_core/runtime.py\nindex 4bce3c3..7210d27 100644\n--- a/cli_core/runtime.py\n+++ b/cli_core/runtime.py\n@@ -112,9 +112,24 @@ def run_agent_turn(\n             for tool_call in tool_calls:\n                 tool_name = tool_call.get(\"name\")\n                 tool = tools_by_name.get(tool_name)\n-                if tool is None:\n+                state = context.state if isinstance(context.state, dict) else {}\n+                if (\n+                    tool_name == \"memory_upsert\"\n+                    and isinstance(state, dict)\n+                    and int(state.get(\"turn_memory_write_count\", 0)) >= 1\n+                ):\n+                    tool_output = (\n+                        \"Memory write skipped: only one memory_upsert call is \"\n+                        \"allowed per turn.\"\n+                    )\n+                elif tool is None:\n                     tool_output: Any = f\"Unknown tool: {tool_name}\"\n                 else:\n+                    if tool_name == \"memory_upsert\" and isinstance(state, dict):\n+                        state[\"turn_memory_write_count\"] = (\n+                            int(state.get(\"turn_memory_write_count\", 0)) + 1\n+                        )\n+                        context.state = state\n                     try:\n                         tool_output = tool.invoke(tool_call.get(\"args\", {}))\n                     except ValidationError as exc:\ndiff --git a/main.py b/main.py\nindex c4f41b4..e8b2f42 100644\n--- a/main.py\n+++ b/main.py\n@@ -5,6 +5,8 @@ import sys\n from pathlib import Path\n from typing import Any\n \n+from langchain_core.tools import tool\n+\n from cli_core import (\n     RendererConfig,\n     RuntimeContext,\n@@ -16,18 +18,36 @@ from cli_core import (\n     log_env_loaded,\n     run_cli,\n )\n+from cli_core.lt_memory import JsonlLongTermMemoryStore\n from cli_core.providers.base import MissingEnvError\n \n DEFAULT_USER_ID = \"default-user\"\n DEFAULT_THREAD_ID = \"default-thread\"\n ENV_OVERRIDE_VAR = \"MEMCLI_ENV_PATH\"\n CHECKPOINT_DB = Path(\"data/checkpoints.sqlite\")\n+LT_MEMORY_DIR = Path(\"data/memory\")\n+LT_RETRIEVAL_K = 3\n \n \n-def build_prompt(_context) -> str:\n+def build_prompt(context: RuntimeContext) -> str:\n+    state = context.state if isinstance(context.state, dict) else {}\n+    records = state.get(\"lt_recent_records\", [])\n+    memory_lines = []\n+    for record in records:\n+        content = str(record.get(\"content\", \"\")).strip()\n+        if not content:\n+            continue\n+        kind = str(record.get(\"kind\", \"semantic\")).strip() or \"semantic\"\n+        memory_lines.append(f\"- [{kind}] {content}\")\n+    known_memory_block = \"\\n\".join(memory_lines) if memory_lines else \"(none)\"\n     return (\n         \"You are a helpful assistant. Keep answers concise unless asked to expand.\\n\"\n-        \"Use the conversation history to resolve follow-ups and pronouns.\"\n+        \"Use the conversation history to resolve follow-ups and pronouns.\\n\\n\"\n+        \"You may call tool `memory_upsert` to store durable user facts/preferences/\"\n+        \"constraints for future sessions. Only store stable information likely useful \"\n+        \"later. Do not store one-off chatter, transient requests, or uncertain facts.\\n\\n\"\n+        \"Known memory (optional context, may be stale):\\n\"\n+        f\"{known_memory_block}\"\n     )\n \n \n@@ -56,12 +76,22 @@ def _clear_session_state(context: RuntimeContext) -> str:\n \n \n def _clear_memory_state(context: RuntimeContext) -> str:\n-    # Stage 1 hook: LT storage internals are added in later stages.\n     state = context.state if isinstance(context.state, dict) else {}\n-    if state.get(\"memory_cleared\", False):\n+    identity = state.get(\"identity\", {})\n+    user_id = identity.get(\"user_id\", DEFAULT_USER_ID)\n+    store = state.get(\"lt_store\")\n+    if store is None or not hasattr(store, \"clear\"):\n         return \"Memory already clear for active user (no persisted memory to remove).\"\n-    state[\"memory_cleared\"] = True\n+\n+    try:\n+        cleared = bool(store.clear(user_id))\n+    except Exception as exc:  # noqa: BLE001\n+        return f\"Memory clear warning for active user: {exc}\"\n+\n+    state[\"lt_recent_records\"] = []\n     context.state = state\n+    if not cleared:\n+        return \"Memory already clear for active user (no persisted memory to remove).\"\n     return \"Memory cleared for active user.\"\n \n \n@@ -108,6 +138,75 @@ def _on_after_turn(context: RuntimeContext, _new_messages) -> None:\n         )\n \n \n+def _on_before_turn(context: RuntimeContext, _user_text: str) -> None:\n+    state = context.state if isinstance(context.state, dict) else {}\n+    identity = state.get(\"identity\", {})\n+    user_id = identity.get(\"user_id\", DEFAULT_USER_ID)\n+    thread_id = identity.get(\"thread_id\", DEFAULT_THREAD_ID)\n+    state[\"turn_counter\"] = int(state.get(\"turn_counter\", 0)) + 1\n+    state[\"active_turn_id\"] = f\"{thread_id}:{state['turn_counter']}\"\n+    state[\"turn_memory_write_count\"] = 0\n+\n+    store = state.get(\"lt_store\")\n+    if store is None or not hasattr(store, \"load_recent\"):\n+        state[\"lt_recent_records\"] = []\n+        context.state = state\n+        return\n+\n+    try:\n+        state[\"lt_recent_records\"] = store.load_recent(user_id, k=LT_RETRIEVAL_K)\n+    except Exception as exc:  # noqa: BLE001\n+        print(f\"Long-term memory retrieval warning for active user: {exc}\")\n+        state[\"lt_recent_records\"] = []\n+    context.state = state\n+\n+\n+def _build_memory_upsert_tool(\n+    state: dict[str, Any],\n+    store: JsonlLongTermMemoryStore,\n+):\n+    @tool\n+    def memory_upsert(\n+        content: str,\n+        kind: str = \"semantic\",\n+        confidence: float | None = None,\n+        source_turn_id: str | None = None,\n+    ) -> str:\n+        \"\"\"Store durable user memory for use across sessions.\n+\n+        Save only stable user facts/preferences/constraints likely useful in future turns.\n+        Skip one-off chatter, transient requests, and uncertain information.\n+        \"\"\"\n+\n+        cleaned = content.strip()\n+        if not cleaned:\n+            return \"Memory write skipped: content is empty.\"\n+\n+        identity = state.get(\"identity\", {})\n+        user_id = identity.get(\"user_id\", DEFAULT_USER_ID)\n+        turn_id = source_turn_id or str(state.get(\"active_turn_id\", \"\")).strip() or None\n+        memory_kind = kind.strip() or \"semantic\"\n+        try:\n+            record = store.append(\n+                user_id=user_id,\n+                content=cleaned,\n+                kind=memory_kind,\n+                confidence=confidence,\n+                source_turn_id=turn_id,\n+            )\n+        except Exception as exc:  # noqa: BLE001\n+            return (\n+                \"Memory write failed for active user. \"\n+                f\"The session will continue without durable memory for this turn: {exc}\"\n+            )\n+        return (\n+            f\"Memory saved for active user. id={record['id']} \"\n+            f\"kind={record['kind']}.\"\n+        )\n+\n+    return memory_upsert\n+\n+\n def main() -> None:\n     trace_enabled = is_env_enabled([\"CLI_TRACE_REQUEST\"])\n     repo_root = Path(__file__).resolve().parent\n@@ -141,11 +240,14 @@ def main() -> None:\n         sys.exit(1)\n \n     checkpoint_store = SqliteCheckpointStore(repo_root / CHECKPOINT_DB)\n+    lt_store = JsonlLongTermMemoryStore(repo_root / LT_MEMORY_DIR)\n     state: dict[str, Any] = {\n         \"identity\": _load_identity(),\n-        \"memory_cleared\": False,\n         \"checkpoint_store\": checkpoint_store,\n+        \"lt_store\": lt_store,\n+        \"lt_recent_records\": [],\n     }\n+    tools.register(_build_memory_upsert_tool(state, lt_store))\n     thread_id = state[\"identity\"][\"thread_id\"]\n     try:\n         state[\"restored_from_checkpoint\"] = checkpoint_store.load(thread_id)\n@@ -162,6 +264,7 @@ def main() -> None:\n         },\n         on_start=_on_start,\n         on_reset=_handle_reset,\n+        on_before_turn=_on_before_turn,\n         on_after_turn=_on_after_turn,\n         renderer=RendererConfig(assistant_label=\"Agent\", user_label=\"You\"),\n         trace_requests=trace_enabled,"
}
```

```bash
source .venv/bin/activate
python3 -m py_compile $(rg --files -g '*.py')
printf '/exit\n' | python3 main.py
git status --short
git diff -- main.py cli_core/runtime.py
git diff --no-index /dev/null cli_core/lt_memory.py
```

Open questions:
- None.
