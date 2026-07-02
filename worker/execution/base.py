# SPDX-License-Identifier: Apache-2.0
"""Backend abstraction for worker task execution.

Each backend implements the same set of operations so the worker daemon
does not need to know whether tasks run on the host or inside a container.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from worker.executor.base import ExecResult
from shared.protocol import ErrorCode


class ExecutionBackend(ABC):
    """Interface for task execution backends."""

    def _resolve_workspace_path(self, workspace: str, sub_path: str) -> tuple[Path, str | None]:
        """Resolve *sub_path* relative to *workspace* and check for escape.

        Returns (resolved_path, None) on success, or (None, error_code) if the
        path escapes the workspace.
        """
        base = Path(workspace).resolve()
        resolved = (base / sub_path).resolve()
        try:
            resolved.relative_to(base)
        except ValueError:
            return None, ErrorCode.workspace_violation.value
        return resolved, None

    @abstractmethod
    async def run_shell(self, command: str, cwd: str | None,
                        timeout: int) -> ExecResult:
        """Execute a shell command."""

    @abstractmethod
    async def read_file(self, path: str) -> ExecResult:
        """Read a file and return its content."""

    @abstractmethod
    async def write_file(self, path: str, content: str) -> ExecResult:
        """Write content to a file."""

    @abstractmethod
    async def list_dir(self, path: str) -> ExecResult:
        """List directory contents."""

    @abstractmethod
    async def system_info(self) -> ExecResult:
        """Gather host system information."""
