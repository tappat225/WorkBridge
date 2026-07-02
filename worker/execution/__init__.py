# SPDX-License-Identifier: Apache-2.0
"""Execution backends for the CapOwn Worker.

The worker daemon selects a backend at startup based on its configured
execution mode and delegates all task execution to it.
"""

from .base import ExecutionBackend
from .host import HostExecutionBackend
from .docker import DockerExecutionBackend

__all__ = [
    "ExecutionBackend",
    "HostExecutionBackend",
    "DockerExecutionBackend",
    "create_backend",
]


def create_backend(
    execution_mode: str,
    workspace: str,
    command_timeout: int = 120,
    container_name: str = "capown-worker",
) -> ExecutionBackend:
    """Create the appropriate execution backend for the given mode.

    Args:
        execution_mode: ``"host"`` or ``"container"``.
        workspace: Workspace path for path resolution inside the backend.
        command_timeout: Default command timeout in seconds.
        container_name: Managed Docker container name (container mode only).

    Returns:
        A configured ``ExecutionBackend`` instance.
    """
    if execution_mode == "container":
        return DockerExecutionBackend(
            workspace=workspace,
            container_name=container_name,
            command_timeout=command_timeout,
        )
    return HostExecutionBackend(
        workspace=workspace,
        command_timeout=command_timeout,
    )
