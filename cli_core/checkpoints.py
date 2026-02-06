from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List

from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict


class CheckpointStoreError(RuntimeError):
    pass


class SqliteCheckpointStore:
    def __init__(self, db_path: Path) -> None:
        self.path = db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS thread_checkpoints (
                        thread_id TEXT PRIMARY KEY,
                        history_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
        except sqlite3.Error as exc:
            raise CheckpointStoreError(
                f"failed to initialize checkpoint database at {self.path}: {exc}"
            ) from exc

    def load(self, thread_id: str) -> List[BaseMessage]:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT history_json FROM thread_checkpoints WHERE thread_id = ?",
                    (thread_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise CheckpointStoreError(
                f"failed reading checkpoint for thread '{thread_id}': {exc}"
            ) from exc

        if row is None:
            return []

        try:
            payload = json.loads(row[0])
            return list(messages_from_dict(payload))
        except Exception as exc:  # noqa: BLE001
            raise CheckpointStoreError(
                f"failed decoding checkpoint payload for thread '{thread_id}': {exc}"
            ) from exc

    def save(self, thread_id: str, history: List[BaseMessage]) -> None:
        try:
            payload = json.dumps(messages_to_dict(history))
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO thread_checkpoints (thread_id, history_json, updated_at)
                    VALUES (?, ?, datetime('now'))
                    ON CONFLICT(thread_id) DO UPDATE SET
                        history_json = excluded.history_json,
                        updated_at = datetime('now')
                    """,
                    (thread_id, payload),
                )
        except sqlite3.Error as exc:
            raise CheckpointStoreError(
                f"failed writing checkpoint for thread '{thread_id}': {exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise CheckpointStoreError(
                f"failed serializing checkpoint for thread '{thread_id}': {exc}"
            ) from exc

    def clear(self, thread_id: str) -> bool:
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM thread_checkpoints WHERE thread_id = ?",
                    (thread_id,),
                )
                return (cursor.rowcount or 0) > 0
        except sqlite3.Error as exc:
            raise CheckpointStoreError(
                f"failed clearing checkpoint for thread '{thread_id}': {exc}"
            ) from exc
