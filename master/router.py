# SPDX-License-Identifier: AGPL-3.0-only
"""Task router: dispatches tasks and matches results."""

import asyncio
import logging
from typing import Optional

from shared.protocol import ErrorCode, Task, TaskMetadata, TaskResult, TaskStatus, TASK_TYPE_TO_CAPABILITY

from .broker import Broker
from .task_store import TaskStore

logger = logging.getLogger(__name__)


class Router:
    # Max entries and TTL for in-memory result cache
    _RESULT_CACHE_MAX = 1000
    _RESULT_CACHE_TTL = 300.0  # seconds

    def __init__(self, broker: Broker, task_store: TaskStore = None):
        self._broker = broker
        self._store = task_store or TaskStore()
        self._pending: dict[str, asyncio.Future] = {}
        self._results: dict[str, TaskResult] = {}
        self._result_timestamps: dict[str, float] = {}

    async def dispatch(self, task: Task) -> bool:
        """Push task to target node via broker. Returns False if node offline."""
        if not self._broker.is_connected(task.target_node):
            return False

        # Record minimal metadata before dispatching
        capability = TASK_TYPE_TO_CAPABILITY.get(task.payload.task_type, "")
        payload_str = task.payload.model_dump_json()
        self._store.create(
            task_id=task.task_id,
            target_node=task.target_node,
            capability=capability.value if capability else "",
            status=TaskStatus.dispatched.value,
            payload_size=len(payload_str),
        )

        fut = asyncio.get_event_loop().create_future()
        self._pending[task.task_id] = fut

        sent = await self._broker.push(task.target_node, "task", task.model_dump(mode="json"))
        if not sent:
            self._pending.pop(task.task_id, None)
            self._store.update_status(task.task_id, TaskStatus.failed.value,
                                       error_code="node_offline")
            return False

        logger.info("router: dispatched task %s to %s", task.task_id, task.target_node)
        return True

    async def wait_result(self, task_id: str, timeout: int = 120) -> Optional[TaskResult]:
        """Wait for task result with timeout."""
        fut = self._pending.get(task_id)
        if not fut:
            return self._results.get(task_id)
        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(task_id, None)
            self._store.update_status(task_id, TaskStatus.timeout.value,
                                       error_code=ErrorCode.timeout.value)
            return TaskResult(
                task_id=task_id, node_id="",
                status=TaskStatus.timeout,
                error="task timed out",
                error_code=ErrorCode.timeout.value)

    def submit_result(self, result: TaskResult):
        """Called when worker reports back."""
        self._results[result.task_id] = result
        self._result_timestamps[result.task_id] = asyncio.get_event_loop().time()
        fut = self._pending.pop(result.task_id, None)
        if fut and not fut.done():
            fut.set_result(result)
        # Persist metadata update
        self._store.update_status(
            result.task_id, result.status.value,
            error_code=result.error_code,
            result_size=len(result.output.encode("utf-8")),
        )
        self._evict_old_results()
        logger.info("router: result for task %s: %s", result.task_id, result.status)

    def _evict_old_results(self):
        """Evict expired or excess entries from the result cache."""
        now = asyncio.get_event_loop().time()
        # Remove expired entries
        expired = [
            tid for tid, ts in self._result_timestamps.items()
            if now - ts > self._RESULT_CACHE_TTL
        ]
        for tid in expired:
            self._results.pop(tid, None)
            self._result_timestamps.pop(tid, None)
        # Enforce max size (drop oldest first)
        while len(self._results) > self._RESULT_CACHE_MAX:
            oldest = min(self._result_timestamps, key=self._result_timestamps.get)
            self._results.pop(oldest, None)
            self._result_timestamps.pop(oldest, None)

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        # Check expiry
        ts = self._result_timestamps.get(task_id)
        if ts is not None:
            now = asyncio.get_event_loop().time()
            if now - ts > self._RESULT_CACHE_TTL:
                self._results.pop(task_id, None)
                self._result_timestamps.pop(task_id, None)
                return None
        return self._results.get(task_id)

    def get_task_metadata(self, task_id: str) -> Optional[TaskMetadata]:
        """Return persisted metadata for a task (no payload/result body)."""
        return self._store.get(task_id)
