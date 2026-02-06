```yaml
review_packet:
  change_id: "DEC-02-05-STAGE4-RUNTIME-HARDENING-HARNESS"
  objective: "Harden runtime reliability/reviewability by reusing model bind per session, guaranteeing spinner cleanup on failures, failing open on turn-level model errors, and adding scripted acceptance/regression harness coverage for Stage 1-3 invariants."
  rationale: "Close known runtime lifecycle and error-path gaps while preserving Stage 1-3 behavior and Kimi/env contracts."
  contract_ref:
    decision_id: "DEC-02-05-STAGE4-RUNTIME-HARDENING-HARNESS"
    stage_objective: "Runtime hardening + acceptance harness + reviewer-facing docs without changing Stage 1-3 feature contracts."
  files_changed:
    - path: "cli_core/runtime.py"
      lines_touched: [31, 60, 87, 181, 229, 240, 247]
    - path: "scripts/stage4_acceptance.py"
      lines_touched: [1, 33, 76, 96, 121, 159, 183, 212]
    - path: "scripts/run_stage4_acceptance.sh"
      lines_touched: [1, 7, 13, 16]
    - path: "README.md"
      lines_touched: [1, 10, 18, 38, 52]
    - path: "stage4-harness-output.txt"
      lines_touched: [1]
    - path: "stage4-review-report.md"
      lines_touched: [1]
  behavioral_changes:
    - "`run_agent_turn` now builds/binds the model once per CLI session and reuses the bound model across subsequent turns."
    - "`stream_model_turn` now wraps stream handling in `try/finally`, always setting stop_event, joining the indicator thread, and clearing the line on success/failure."
    - "`run_cli` now catches turn-level model invocation exceptions, emits actionable turn error text, restores pre-turn history, and keeps the process alive."
    - "Added deterministic Stage 4 harness script validating startup command surface, spinner cleanup, forced stream-failure recovery, model reuse, and Stage 2/3 restore/isolation/clear invariants."
    - "README now includes reviewer runbook for contracts, startup, and Stage 4 harness execution."
  risks:
    level: "low"
    notes: "Harness forced-failure checks use fakes/patching for determinism; they validate runtime behavior boundaries but are not an external provider integration test."
  tests:
    commands:
      - "python3 -m py_compile $(rg --files -g '*.py')"
      - "./scripts/run_stage4_acceptance.sh"
      - "git status --short"
      - "git diff -- README.md cli_core/runtime.py"
      - "git diff --no-index /dev/null scripts/run_stage4_acceptance.sh"
      - "git diff --no-index /dev/null scripts/stage4_acceptance.py"
    results: "pass"
  acceptance_evidence:
    - check: "python3 -m py_compile $(rg --files -g '*.py')"
      command: "python3 -m py_compile $(rg --files -g '*.py')"
      result: "pass"
      proof: "Exit code 0."
    - check: "Startup still prints command surface /session-clear /memory-clear /reset /paste /exit"
      command: "./scripts/run_stage4_acceptance.sh (startup command surface check)"
      result: "pass"
      proof: "Harness output includes: commands: /session-clear /memory-clear /reset /paste /exit"
    - check: "Forced stream/model failure path emits actionable turn error and process stays usable for next turn"
      command: "./scripts/run_stage4_acceptance.sh (turn error fail-open + model reuse check)"
      result: "pass"
      proof: "Harness asserts output contains 'Turn error: model invocation failed.' and subsequent 'Recovered response'."
    - check: "Spinner cleanup is guaranteed on stream failure"
      command: "./scripts/run_stage4_acceptance.sh (spinner cleanup on stream failure check)"
      result: "pass"
      proof: "Harness proof: stop_event_set=True; join_calls=1 on forced stream failure path."
    - check: "Model build/bind is reused per session (not rebuilt each steady-state turn)"
      command: "./scripts/run_stage4_acceptance.sh (turn error fail-open + model reuse check)"
      result: "pass"
      proof: "Harness proof: build_calls=1, bind_calls=1, stream_calls=2 across two turns."
    - check: "Stage 2 ST restore/isolation checks still pass"
      command: "./scripts/run_stage4_acceptance.sh (stage2 ST restore/isolation check)"
      result: "pass"
      proof: "Harness verifies per-thread restore, isolation, and idempotent clear semantics."
    - check: "Stage 3 LT restore/isolation/clear checks still pass"
      command: "./scripts/run_stage4_acceptance.sh (stage3 LT restore/isolation/clear check)"
      result: "pass"
      proof: "Harness verifies per-user restore/isolation and idempotent clear semantics."
  manual_checks:
    - step: "Run rails report gate"
      expected: "PASS verify-report"
    - step: "Capture repository evidence"
      expected: "`git status --short` and `git diff` outputs included in handoff"
  diagnostics_added:
    - name: "stage4_harness"
      fields: ["startup command surface", "spinner cleanup", "turn failure recovery", "model reuse counters", "ST/LT regression status"]
  rollback:
    - "git restore -- README.md cli_core/runtime.py"
    - "rm -f scripts/stage4_acceptance.py scripts/run_stage4_acceptance.sh stage4-harness-output.txt stage4-review-report.md"
```

```json
{
  "collected_at": "2026-02-06T02:54:47.067564Z",
  "git_root": "/Users/junho/agents/mem-cli",
  "branch": "main",
  "head_sha": "f78fed0db161c6726f3778d21bf116d8ad74151d",
  "recent_commits": "f78fed0 docs: add stage 4 runtime hardening contract\ned2809a feat: implement stage 3 long-term memory contracts\nfb901d1 feat: implement stage 2 short-term checkpoint persistence\n71583f0 feat: implement stage 1 runtime contracts and commands\n3eda318 chore: finalize baseline cli labels and trace wiring\n201d7d6 docs: lock architecture decisions and staged implementation plan\nfd1767d chore: bootstrap cli core",
  "status_porcelain": "M README.md\n M cli_core/runtime.py\n?? data/\n?? scripts/\n?? stage4-harness-output.txt\n?? stage4-review-report.md",
  "range_used": null,
  "diff_stat": "README.md           | 54 +++++++++++++++++++++++++++++++++++++++++++++--\n cli_core/runtime.py | 61 ++++++++++++++++++++++++++++++++++-------------------\n 2 files changed, 91 insertions(+), 24 deletions(-)",
  "diff": "diff --git a/README.md b/README.md\nindex e4b67e2..9cd38ab 100644\n--- a/README.md\n+++ b/README.md\n@@ -1,5 +1,55 @@\n # mem-cli\n \n-Baseline CLI core for a minimal LangChain-based conversational agent.\n+Minimal LangChain-based CLI conversational agent with:\n \n-This repo will be built incrementally to implement short-term and long-term memory.\n+- Stage 1 runtime contracts and reset commands\n+- Stage 2 short-term memory (thread-scoped sqlite checkpoints)\n+- Stage 3 long-term memory (user-scoped JSONL records)\n+- Stage 4 runtime hardening + scripted acceptance harness\n+\n+## Runtime contracts\n+\n+- Provider policy: Kimi/Moonshot only.\n+- Env loading: repo-local `.env` (or explicit `MEMCLI_ENV_PATH` override), no parent traversal.\n+- Identity defaults: `MEMCLI_USER_ID=default-user`, `MEMCLI_THREAD_ID=default-thread`.\n+- Commands: `/session-clear`, `/memory-clear`, `/reset`, `/paste`, `/exit`.\n+- Clear commands and `/reset` are non-interactive and idempotent.\n+\n+## Quick start\n+\n+```bash\n+python3 -m venv .venv\n+source .venv/bin/activate\n+pip install -r requirements.txt\n+python3 main.py\n+```\n+\n+Required env:\n+\n+- `MOONSHOT_API_KEY` (startup fails fast if missing)\n+\n+Optional env:\n+\n+- `MEMCLI_PROVIDER` (`moonshot`/`kimi`; other values are rejected)\n+- `MEMCLI_USER_ID`\n+- `MEMCLI_THREAD_ID`\n+- `MEMCLI_ENV_PATH`\n+\n+## Stage 4 acceptance harness\n+\n+Run all Stage 4 acceptance checks (plus Stage 1-3 regression checks):\n+\n+```bash\n+./scripts/run_stage4_acceptance.sh\n+```\n+\n+Direct harness invocation:\n+\n+```bash\n+python3 scripts/stage4_acceptance.py\n+```\n+\n+## Data layout\n+\n+- ST checkpoints: `data/checkpoints.sqlite`\n+- LT memory: `data/memory/{user_id}.jsonl`\ndiff --git a/cli_core/runtime.py b/cli_core/runtime.py\nindex 7210d27..c1f2efd 100644\n--- a/cli_core/runtime.py\n+++ b/cli_core/runtime.py\n@@ -34,6 +34,8 @@ class RuntimeContext:\n     history: List[BaseMessage] = field(default_factory=list)\n     state: Any = None\n     trace_requests: bool = False\n+    session_model: Any = None\n+    session_bound_model: Any = None\n \n \n CommandHandler = Callable[[RuntimeContext, str], bool]\n@@ -63,20 +65,20 @@ def stream_model_turn(\n     stop_event = __import__(\"threading\").Event()\n     indicator_thread = start_thinking_indicator(stop_event)\n     chunk_accumulator: Optional[AIMessageChunk] = None\n-\n-    if run_config:\n-        stream_iter = bound_model.stream(messages, config=run_config)\n-    else:\n-        stream_iter = bound_model.stream(messages)\n-    for chunk in stream_iter:\n-        if chunk_accumulator is None:\n-            chunk_accumulator = chunk\n+    try:\n+        if run_config:\n+            stream_iter = bound_model.stream(messages, config=run_config)\n         else:\n-            chunk_accumulator += chunk\n-\n-    stop_event.set()\n-    indicator_thread.join(timeout=1)\n-    clear_line()\n+            stream_iter = bound_model.stream(messages)\n+        for chunk in stream_iter:\n+            if chunk_accumulator is None:\n+                chunk_accumulator = chunk\n+            else:\n+                chunk_accumulator += chunk\n+    finally:\n+        stop_event.set()\n+        indicator_thread.join(timeout=1)\n+        clear_line()\n     if chunk_accumulator is None:\n         return AIMessage(content=\"\")\n     return message_chunk_to_message(chunk_accumulator)  # type: ignore[return-value]\n@@ -89,9 +91,15 @@ def run_agent_turn(\n     tool_postprocessor: Optional[ToolPostprocessor] = None,\n ) -> List[BaseMessage]:\n     tools_by_name = tool_registry.by_name()\n-    model = context.adapter.build_model()\n-    maybe_trace_request_payload(model, context.trace_requests)\n-    bound_model = context.adapter.bind_tools(model, tool_registry.all())\n+    if context.session_bound_model is None:\n+        model = context.adapter.build_model()\n+        maybe_trace_request_payload(model, context.trace_requests)\n+        context.session_model = model\n+        context.session_bound_model = context.adapter.bind_tools(\n+            model,\n+            tool_registry.all(),\n+        )\n+    bound_model = context.session_bound_model\n     messages: List[BaseMessage] = list(context.history)\n     system_message = SystemMessage(content=system_prompt)\n     run_config = build_langsmith_run_config(context.adapter)\n@@ -220,6 +228,7 @@ def run_cli(\n \n         print_user_block(user_text, options.renderer)\n         print()\n+        history_before_turn = list(context.history)\n         context.history.append(HumanMessage(content=user_text))\n         prior_count = len(context.history)\n         start_ms = time.perf_counter_ns()\n@@ -228,12 +237,20 @@ def run_cli(\n             options.on_before_turn(context, user_text)\n \n         system_prompt = options.prompt_builder(context)\n-        updated_history = run_agent_turn(\n-            context=context,\n-            system_prompt=system_prompt,\n-            tool_registry=options.tool_registry,\n-            tool_postprocessor=options.tool_postprocessor,\n-        )\n+        try:\n+            updated_history = run_agent_turn(\n+                context=context,\n+                system_prompt=system_prompt,\n+                tool_registry=options.tool_registry,\n+                tool_postprocessor=options.tool_postprocessor,\n+            )\n+        except Exception as exc:  # noqa: BLE001\n+            context.history = history_before_turn\n+            print(\n+                \"Turn error: model invocation failed. \"\n+                f\"Please retry or adjust input. Detail: {exc}\"\n+            )\n+            continue\n         new_messages = updated_history[prior_count:]\n         context.history = updated_history\n         pretty_print_assistant(new_messages, options.renderer)"
}

```

```bash
python3 -m py_compile $(rg --files -g '*.py')
./scripts/run_stage4_acceptance.sh
git status --short
git diff -- README.md cli_core/runtime.py
git diff --no-index /dev/null scripts/run_stage4_acceptance.sh
git diff --no-index /dev/null scripts/stage4_acceptance.py
RAILS_HOME="${CODEX_HOME:-$HOME/.codex}/rails"
"$RAILS_HOME/verify-report" stage4-review-report.md
```

Open questions:
- None.
