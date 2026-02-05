from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .providers.base import ProviderAdapter


def maybe_trace_request_payload(model: Any, enabled: bool) -> None:
    if not enabled:
        return
    client = getattr(model, "client", None)
    if client is None or not hasattr(client, "create"):
        print("[trace] request logging unavailable: no client.create found")
        return
    if getattr(client.create, "_cli_core_wrapped", False):
        return

    original_create = client.create

    def wrapped_create(**payload: Any) -> Any:
        print("[trace] request payload keys:", sorted(payload.keys()))
        if "model" in payload:
            print("[trace] model:", payload.get("model"))
        if "messages" in payload:
            print("[trace] messages:", len(payload.get("messages") or []))
        if "tools" in payload:
            tool_names = [tool.get("function", {}).get("name") for tool in payload["tools"]]
            print("[trace] tools:", tool_names)
        if "extra_body" in payload:
            print("[trace] extra_body:", payload.get("extra_body"))
        return original_create(**payload)

    wrapped_create._cli_core_wrapped = True  # type: ignore[attr-defined]
    client.create = wrapped_create


def _parse_langsmith_pricing() -> Optional[Dict[str, Any]]:
    raw = __import__("os").environ.get("LANGSMITH_MODEL_PRICING_JSON")
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print("[trace] invalid LANGSMITH_MODEL_PRICING_JSON")
        return None
    if not isinstance(parsed, dict):
        print("[trace] LANGSMITH_MODEL_PRICING_JSON must be a JSON object")
        return None
    return parsed


def build_langsmith_run_config(adapter: ProviderAdapter) -> Optional[Dict[str, Any]]:
    pricing = _parse_langsmith_pricing()
    if not pricing:
        return None
    metadata = {
        "model_pricing_json": json.dumps(pricing, separators=(",", ":")),
        "model_name": adapter.config.model,
        "provider": adapter.name,
    }
    return {"metadata": metadata}
