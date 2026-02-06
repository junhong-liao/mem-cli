from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class LongTermMemoryStoreError(RuntimeError):
    pass


class JsonlLongTermMemoryStore:
    REQUIRED_FIELDS = {
        "id",
        "user_id",
        "content",
        "kind",
        "created_at",
        "updated_at",
    }

    def __init__(self, memory_dir: Path) -> None:
        self.memory_dir = memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _user_key(self, user_id: str) -> str:
        raw = str(user_id)
        if not raw.strip():
            raise LongTermMemoryStoreError("invalid user_id for long-term memory path")
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _user_path(self, user_id: str) -> Path:
        return self.memory_dir / f"{self._user_key(user_id)}.jsonl"

    def load_recent(self, user_id: str, k: int = 3) -> List[Dict[str, Any]]:
        if k <= 0:
            return []
        path = self._user_path(user_id)
        if not path.exists():
            return []

        records: List[Dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_no, raw_line in enumerate(handle, start=1):
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        parsed = json.loads(line)
                    except json.JSONDecodeError as exc:
                        print(
                            "Long-term memory warning: skipping malformed JSONL "
                            f"line {line_no} in {path}: {exc}"
                        )
                        continue
                    if not isinstance(parsed, dict):
                        print(
                            "Long-term memory warning: skipping invalid record "
                            f"line {line_no} in {path} (JSON value is not an object)."
                        )
                        continue
                    if not self.REQUIRED_FIELDS.issubset(parsed.keys()):
                        print(
                            "Long-term memory warning: skipping invalid record "
                            f"line {line_no} in {path} (missing required fields)."
                        )
                        continue
                    records.append(parsed)
        except OSError as exc:
            raise LongTermMemoryStoreError(
                f"failed reading long-term memory for user '{user_id}': {exc}"
            ) from exc

        if not records:
            return []
        return list(reversed(records[-k:]))

    def append(
        self,
        user_id: str,
        content: str,
        kind: str = "semantic",
        confidence: Optional[float] = None,
        source_turn_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        record: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "content": content,
            "kind": kind,
            "created_at": now,
            "updated_at": now,
        }
        if confidence is not None:
            record["confidence"] = confidence
        if source_turn_id:
            record["source_turn_id"] = source_turn_id

        path = self._user_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=True))
                handle.write("\n")
        except OSError as exc:
            raise LongTermMemoryStoreError(
                f"failed writing long-term memory for user '{user_id}': {exc}"
            ) from exc

        return record

    def clear(self, user_id: str) -> bool:
        path = self._user_path(user_id)
        if not path.exists():
            return False
        try:
            path.unlink()
        except OSError as exc:
            raise LongTermMemoryStoreError(
                f"failed clearing long-term memory for user '{user_id}': {exc}"
            ) from exc
        return True
