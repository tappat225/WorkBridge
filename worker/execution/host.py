# SPDX-License-Identifier: Apache-2.0
"""Host execution backend — tasks run directly on the host system."""

from typing import Any

from .base import ExecutionBackend
from worker.executor.base import ExecResult
from worker.executor.shell import ShellExecutor
from worker.executor.file import FileExecutor
from worker.executor.system_info import SystemInfoExecutor


class HostExecutionBackend(ExecutionBackend):
    """Execution backend that runs tasks natively on the host.

    Delegates to the existing ShellExecutor, FileExecutor, and
    SystemInfoExecutor while preserving workspace boundary enforcement
    and timeout protection.
    """

    def __init__(self, workspace: str, command_timeout: int = 120):
        # File and sysinfo executors need no per-call timeout,
        # but ShellExecutor is created fresh per call so the
        # per-task ``timeout`` argument is honoured.
        self._file = FileExecutor(workspace)
        self._sysinfo = SystemInfoExecutor()
        self._workspace = workspace
        self._timeout = command_timeout

    async def run_shell(self, command: str, cwd: str | None,
                        timeout: int) -> ExecResult:
        # Create a fresh executor per call with the effective timeout
        # so host and container backends behave identically.
        executor = ShellExecutor(self._workspace, timeout)
        params: dict[str, Any] = {"command": command}
        if cwd:
            params["cwd"] = cwd
        return await executor.execute(params)

    async def read_file(self, path: str) -> ExecResult:
        return await self._file.execute({"action": "read", "path": path})

    async def write_file(self, path: str, content: str) -> ExecResult:
        return await self._file.execute({
            "action": "write", "path": path, "content": content,
        })

    async def list_dir(self, path: str) -> ExecResult:
        return await self._file.execute({"action": "list", "path": path})

    async def system_info(self) -> ExecResult:
        return await self._sysinfo.execute({})
