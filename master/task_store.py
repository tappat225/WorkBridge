# SPDX-License-Identifier: AGPL-3.0-only
"""Task metadata store — persists minimal task routing info, NOT payload/result body.

This store explicitly avoids storing sensitive content such as command text,
file content, or full stdout/stderr. See Phase 2 of the development plan.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

from shared.protocol import TaskMetadata, TaskStatus, TASK_TYPE_TO_CAPABILITY


class TaskStore:
    """Persistent task metadata store backed by SQLite."""

    def __init__(self, db_path: str = "tasks.db"):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn_obj: sqlite3.Connection | None = None
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        if self._conn_obj is None:
            self._conn_obj = sqlite3.connect(self._db_path, timeout=2)
            self._conn_obj.row_factory = sqlite3.Row
        return self._conn_obj

    def close(self):
        """Close the underlying database connection."""
        with self._lock:
            if self._conn_obj is not None:
                self._conn_obj.close()
                self._conn_obj = None

    def _init_db(self):
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_metadata (
                task_id TEXT PRIMARY KEY,
                target_node TEXT NOT NULL,
                capability TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_code TEXT,
                payload_size INTEGER NOT NULL DEFAULT 0,
                result_size INTEGER NOT NULL DEFAULT 0
            )
        """)

    def create(self, task_id: str, target_node: str,
               capability: str = "", status: str = "pending",
               payload_size: int = 0) -> TaskMetadata:
        """Record a new task's metadata. Returns the created record."""
        now = _now()
        conn = self._conn()
        with self._lock:
            conn.execute(
                """INSERT INTO task_metadata
                   (task_id, target_node, capability, status, created_at, updated_at,
                    error_code, payload_size, result_size)
                   VALUES (?, ?, ?, ?, ?, ?, NULL, ?, 0)""",
                (task_id, target_node, capability, status, now, now, payload_size),
            )
            conn.commit()
        return self.get(task_id)

    def update_status(self, task_id: str, status: str,
                      error_code: Optional[str] = None,
                      result_size: int = 0) -> bool:
        """Update task status and optionally error_code / result_size."""
        now = _now()
        conn = self._conn()
        with self._lock:
            cur = conn.execute(
                """UPDATE task_metadata
                   SET status=?, updated_at=?, error_code=COALESCE(?, error_code),
                       result_size=MAX(result_size, ?)
                   WHERE task_id=?""",
                (status, now, error_code, result_size, task_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def get(self, task_id: str) -> Optional[TaskMetadata]:
        """Look up a task by ID. Returns None if not found."""
        row = self._conn().execute(
            "SELECT * FROM task_metadata WHERE task_id=?", (task_id,)
        ).fetchone()
        if not row:
            return None
        return TaskMetadata(
            task_id=row["task_id"],
            target_node=row["target_node"],
            capability=row["capability"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error_code=row["error_code"],
            payload_size=row["payload_size"],
            result_size=row["result_size"],
        )

    def list_by_node(self, node_id: str, limit: int = 20) -> list[TaskMetadata]:
        """List recent tasks for a given node, newest first."""
        rows = self._conn().execute(
            """SELECT * FROM task_metadata
               WHERE target_node=?
               ORDER BY created_at DESC LIMIT ?""",
            (node_id, limit),
        ).fetchall()
        return [TaskMetadata(**dict(r)) for r in rows]

    def list_recent(self, limit: int = 50) -> list[TaskMetadata]:
        """List recent tasks across all nodes, newest first."""
        rows = self._conn().execute(
            "SELECT * FROM task_metadata ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [TaskMetadata(**dict(r)) for r in rows]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
