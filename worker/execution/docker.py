# SPDX-License-Identifier: Apache-2.0
"""Docker execution backend — tasks run inside a managed execution container."""

import asyncio
from pathlib import Path

from .base import ExecutionBackend
from worker.executor.base import ExecResult
from shared.protocol import ErrorCode


class DockerExecutionBackend(ExecutionBackend):
    """Execution backend that runs tasks inside a managed Docker container.

    The container is expected to already exist (created at deploy time).
    The backend uses ``docker exec`` for shell and file operations, never
    ``docker run``, so the task payload cannot control image, mounts,
    network, or privilege settings.

    Workspace boundary enforcement is applied on the host side before
    paths reach Docker commands.
    """

    def __init__(self, workspace: str, container_name: str = "capown-worker",
                 command_timeout: int = 120):
        self._workspace = workspace
        self._container = container_name
        self._timeout = command_timeout

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    async def _run_docker(self, cmd: list[str], timeout: int,
                          input_str: str | None = None) -> ExecResult:
        """Run a docker command with timeout protection.

        *cmd* is the full command list (including ``docker`` as argv[0]).
        Returns an ``ExecResult`` with structured error codes.
        Kills the subprocess on timeout so no orphan process is left running.
        """
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE
                if input_str is not None
                else None,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(
                    input_str.encode("utf-8")
                    if input_str is not None
                    else None
                ),
                timeout=timeout,
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            if proc.returncode == 0:
                return ExecResult(success=True, output=stdout)
            return ExecResult(
                success=False,
                error=stderr.strip() or f"exit code {proc.returncode}",
                error_code=ErrorCode.execution_failed.value,
            )
        except asyncio.TimeoutError:
            if proc is not None:
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=2)
                except Exception:
                    pass
            return ExecResult(
                success=False,
                error=f"command timed out after {timeout}s",
                error_code=ErrorCode.timeout.value,
            )
        except FileNotFoundError:
            return ExecResult(
                success=False,
                error="docker not found on host",
                error_code=ErrorCode.execution_failed.value,
            )
        except Exception as e:
            return ExecResult(success=False, error=str(e))

    def _exec_cmd(self, *args: str) -> list[str]:
        """Build a ``docker exec`` command list targeting the managed container.

        Usage::

            cmd = self._exec_cmd("sh", "-c", "echo hello")
        """
        return ["docker", "exec", "-i", self._container, *args]

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    async def run_shell(self, command: str, cwd: str | None,
                        timeout: int) -> ExecResult:
        """Execute a shell command inside the managed container."""
        cmd = ["docker", "exec"]
        if cwd:
            resolved, err = self._resolve_workspace_path(self._workspace, cwd)
            if err:
                return ExecResult(
                    success=False,
                    error=f"cwd escapes workspace: {cwd}",
                    error_code=err,
                )
            cmd.extend(["-w", str(resolved)])
        cmd.extend(["-i", self._container, "sh", "-c", command])
        return await self._run_docker(cmd, timeout)

    async def read_file(self, path: str) -> ExecResult:
        """Read a file from inside the managed container."""
        resolved, err = self._resolve_workspace_path(self._workspace, path)
        if err:
            return ExecResult(
                success=False,
                error=f"path escapes workspace: {path}",
                error_code=err,
            )
        cmd = self._exec_cmd("cat", str(resolved))
        return await self._run_docker(cmd, self._timeout)

    async def write_file(self, path: str, content: str) -> ExecResult:
        """Write content to a file inside the managed container.

        Paths are passed as argv arguments to ``sh -c``, never interpolated
        into a shell string, to prevent shell injection via crafted paths.
        """
        resolved, err = self._resolve_workspace_path(self._workspace, path)
        if err:
            return ExecResult(
                success=False,
                error=f"path escapes workspace: {path}",
                error_code=err,
            )
        parent = str(resolved.parent)
        target = str(resolved)
        # sh -c 'mkdir -p "$1" && cat > "$2"' sh <parent> <target>
        cmd = self._exec_cmd(
            "sh", "-c", 'mkdir -p "$1" && cat > "$2"',
            "sh", parent, target,
        )
        return await self._run_docker(cmd, self._timeout, input_str=content)

    async def list_dir(self, path: str) -> ExecResult:
        """List directory contents inside the managed container."""
        resolved, err = self._resolve_workspace_path(self._workspace, path)
        if err:
            return ExecResult(
                success=False,
                error=f"path escapes workspace: {path}",
                error_code=err,
            )
        cmd = self._exec_cmd("ls", "-la", str(resolved))
        return await self._run_docker(cmd, self._timeout)

    async def system_info(self) -> ExecResult:
        """Gather system information from the host (not the container).

        The worker control process runs on the host regardless of execution
        mode, so system info reflects the host OS and resources.
        """
        # Construct host info using pure Python
        import platform

        hostname = platform.node()
        system = platform.system()
        release = platform.release()
        machine = platform.machine()

        info_lines = [
            f"hostname: {hostname}",
            f"system: {system}",
            f"release: {release}",
            f"machine: {machine}",
        ]

        if system == "Linux":
            try:
                proc = await asyncio.create_subprocess_exec(
                    "cat", "/etc/os-release",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0:
                    for line in stdout.decode("utf-8", errors="replace").splitlines():
                        if "=" in line:
                            key, val = line.split("=", 1)
                            val = val.strip("\"'")
                            if key in ("ID", "VERSION_ID", "PRETTY_NAME"):
                                info_lines.append(f"os_{key.lower()}: {val}")
            except Exception:
                pass

            try:
                proc = await asyncio.create_subprocess_exec(
                    "free", "-h",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0:
                    mem_lines = stdout.decode("utf-8", errors="replace").splitlines()
                    if len(mem_lines) >= 2:
                        info_lines.append("memory: " + mem_lines[1])
            except Exception:
                pass

        return ExecResult(success=True, output="\n".join(info_lines))
