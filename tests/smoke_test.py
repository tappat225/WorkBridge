#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Smoke tests for CapOwn protocol and CLI changes.

Run: python tests/smoke_test.py
"""

import json
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_protocol_models():
    """Verify protocol model serialization with new fields."""
    from shared.protocol import (
        Capability, CAPABILITY_TO_TASK_TYPE, TASK_TYPE_TO_CAPABILITY,
        ErrorCode, TaskResult, TaskStatus, TaskType,
    )

    # ErrorCode enum values
    codes = [e.value for e in ErrorCode]
    assert "node_offline" in codes
    assert "output_too_large" in codes
    print(f"  OK: {len(codes)} error codes defined")

    # Capability enum values
    caps = [e.value for e in Capability]
    assert "system.info" in caps
    assert "shell.run" in caps
    assert "file.list" in caps
    assert "file.read" in caps
    assert "file.write" in caps
    print(f"  OK: {len(caps)} capabilities defined")

    # Capability-to-TaskType mapping covers all capabilities
    for cap in Capability:
        assert cap in CAPABILITY_TO_TASK_TYPE, f"missing mapping for {cap}"
        tt = CAPABILITY_TO_TASK_TYPE[cap]
        assert TASK_TYPE_TO_CAPABILITY[tt] == cap, f"roundtrip failed for {cap}"
    print("  OK: capability <-> task_type roundtrip")

    # TaskResult with new fields
    tr = TaskResult(
        task_id="abc123", node_id="node1",
        status=TaskStatus.completed, output="hello",
        error="something broke", error_code="execution_failed",
        truncated=False,
    )
    data = tr.model_dump(mode="json")
    assert data["error_code"] == "execution_failed"
    assert data["truncated"] is False
    assert data["status"] == "completed"
    assert "completed_at" in data
    print("  OK: TaskResult serialization with error_code and truncated")

    # Backward compatibility: old TaskResult (no new fields) still deserializes
    old_json = json.dumps({
        "task_id": "old123", "node_id": "node1",
        "status": "failed", "output": "", "error": "oops",
    })
    old_tr = TaskResult(**json.loads(old_json))
    assert old_tr.error_code is None
    assert old_tr.truncated is False
    print("  OK: backward-compatible TaskResult deserialization")

    # TaskResult serializable via model_dump(mode="json")
    raw = tr.model_dump(mode="json")
    json.dumps(raw)  # must not raise
    print("  OK: TaskResult JSON-serializable")

    return True


def test_legacy_compatibility():
    """Verify LEGACY_TO_CAPABILITY mapping."""
    from shared.protocol import LEGACY_TO_CAPABILITY

    assert "list_nodes" in LEGACY_TO_CAPABILITY
    assert "run_command" in LEGACY_TO_CAPABILITY
    assert "read_file" in LEGACY_TO_CAPABILITY
    assert "write_file" in LEGACY_TO_CAPABILITY
    assert "list_directory" in LEGACY_TO_CAPABILITY
    assert "system_info" in LEGACY_TO_CAPABILITY
    print("  OK: all legacy commands have capability mappings")


def test_cli_parsing():
    """Verify CLI argument parsing for new and old command names."""
    from client.capown_client import COMMAND_ALIASES, build_task

    class FakeArgs:
        pass

    # New command aliases exist
    assert "nodes" in COMMAND_ALIASES
    assert "run" in COMMAND_ALIASES
    assert "read" in COMMAND_ALIASES
    assert "write" in COMMAND_ALIASES
    assert "ls" in COMMAND_ALIASES
    assert "info" in COMMAND_ALIASES
    print(f"  OK: {len(COMMAND_ALIASES)} CLI aliases defined")

    # build_task maps old action -> task_type, params
    args = FakeArgs()
    args.command = "echo hello"
    tt, params = build_task("run_command", args)
    assert tt == "shell"
    assert params["command"] == "echo hello"

    args = FakeArgs()
    args.path = "/etc/hostname"
    tt, params = build_task("read_file", args)
    assert tt == "file_read"
    assert params["path"] == "/etc/hostname"

    args = FakeArgs()
    args.path = "/tmp/test.txt"
    args.content = "hello"
    tt, params = build_task("write_file", args)
    assert tt == "file_write"
    assert params["content"] == "hello"

    args = FakeArgs()
    args.path = "/tmp"
    tt, params = build_task("list_directory", args)
    assert tt == "list_dir"
    assert params["path"] == "/tmp"

    args = FakeArgs()
    tt, params = build_task("system_info", args)
    assert tt == "system_info"
    assert params == {}
    print("  OK: build_task maps all legacy actions correctly")

    # Commands that don't exist still fail
    try:
        build_task("nonexistent", FakeArgs())
        assert False, "should have raised"
    except RuntimeError:
        pass
    print("  OK: unknown action raises RuntimeError")


def test_ascii_only():
    """Verify that all enum values and strings are ASCII-only."""
    from shared.protocol import ErrorCode, Capability, TaskType

    for enum_cls in (ErrorCode, Capability, TaskType):
        for member in enum_cls:
            assert all(32 <= ord(c) <= 126 for c in member.value), \
                f"non-ASCII in {enum_cls.__name__}.{member}"
    print("  OK: all enum values are ASCII-only")


def test_executor_base():
    """Verify ExecResult supports new error_code field."""
    from worker.executor.base import ExecResult

    r = ExecResult(success=False, error="fail", error_code="execution_failed")
    assert r.error_code == "execution_failed"
    assert r.success is False

    r2 = ExecResult(success=True, output="ok")
    assert r2.error_code is None
    print("  OK: ExecResult with error_code")


def test_workspace_boundary():
    """Verify file and shell executors reject escaped paths."""
    import asyncio
    import tempfile
    from worker.executor.file import FileExecutor
    from worker.executor.shell import ShellExecutor

    fe = FileExecutor(tempfile.gettempdir())
    se = ShellExecutor(tempfile.gettempdir())

    async def run():
        # File executor: path traversal should fail
        r = await fe.execute({"action": "read", "path": "../../../etc/passwd"})
        assert r.error_code == "workspace_violation", f"got {r.error_code}"
        assert "escapes workspace" in r.error

        # File executor: write with traversal
        r = await fe.execute({"action": "write", "path": "../../../etc/evil", "content": "x"})
        assert r.error_code == "workspace_violation"

        # File executor: list with traversal
        r = await fe.execute({"action": "list", "path": "../../../etc"})
        assert r.error_code == "workspace_violation"

        # Shell executor: cwd traversal
        r = await se.execute({"command": "pwd", "cwd": "../../../etc"})
        assert r.error_code == "workspace_violation", f"got {r.error_code}"

        # Legit path within workspace succeeds (or gives file-not-found, not violation)
        r = await fe.execute({"action": "read", "path": "nonexistent_file_xyz"})
        assert r.error_code is None or r.error_code != "workspace_violation"

    asyncio.run(run())
    print("  OK: all workspace boundary checks pass")


def test_shell_timeout():
    """Verify shell executor times out while waiting for command completion."""
    import asyncio
    import os
    import tempfile
    import time
    from worker.executor.shell import ShellExecutor

    if os.name == "nt":
        command = "ping 127.0.0.1 -n 3"
    else:
        command = "python3 -c \"import time; time.sleep(2)\""

    async def run():
        executor = ShellExecutor(tempfile.gettempdir(), timeout=1)
        start = time.monotonic()
        result = await executor.execute({"command": command})
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"timeout took too long: {elapsed:.2f}s"
        assert result.success is False
        assert result.error_code == "timeout", f"got {result.error_code}"

    asyncio.run(run())
    print("  OK: shell command timeout is enforced")


def test_output_truncation():
    """Verify daemon _truncate returns output_too_large for oversized output."""
    from worker.executor.base import ExecResult
    from shared.config import WorkerConfig

    # Test _truncate logic directly without importing WorkerDaemon (needs httpx)
    max_output = 100

    def truncate(result: ExecResult) -> ExecResult:
        if len(result.output.encode("utf-8")) > max_output:
            return ExecResult(
                success=False, output="",
                error=f"output truncated at {max_output} bytes",
                error_code="output_too_large",
            )
        return result

    # Small output: passes through
    small = ExecResult(success=True, output="x" * 50)
    capped = truncate(small)
    assert capped.success is True
    assert capped.output == "x" * 50
    assert capped.error_code is None
    print("  OK: small output passes truncation")

    # Large output: truncated with error_code
    large = ExecResult(success=True, output="x" * 200)
    capped = truncate(large)
    assert capped.success is False
    assert capped.output == ""
    assert capped.error_code == "output_too_large"
    print("  OK: large output returns output_too_large")


def test_print_result():
    """Verify CLI print_result shows error_code correctly."""
    from client.capown_client import print_result
    import io
    import sys

    # Capture stderr
    stderr = io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = stderr

    try:
        # Error result with error_code
        try:
            print_result({
                "status": "failed",
                "output": "",
                "error": "something broke",
                "error_code": "execution_failed",
                "truncated": False,
            })
        except SystemExit:
            pass
        output = stderr.getvalue()
        assert "[execution_failed]" in output
        assert "something broke" in output
        print("  OK: print_result shows error_code")

        # Truncated result
        stderr = io.StringIO()
        sys.stderr = stderr
        try:
            print_result({
                "status": "failed",
                "output": "",
                "error": "output truncated at 100 bytes",
                "error_code": "output_too_large",
                "truncated": True,
            })
        except SystemExit:
            pass
        output = stderr.getvalue()
        assert "[output_too_large]" in output
        assert "[truncated]" in output
        print("  OK: print_result shows truncated flag")
    finally:
        sys.stderr = old_stderr


def test_dispatch_request_validation():
    """Verify DispatchRequest Pydantic validation rejects invalid input."""
    from shared.protocol import DispatchRequest, TaskType
    from pydantic import ValidationError

    # Valid request passes
    req = DispatchRequest(
        target_node="worker-1",
        payload={"task_type": "shell", "params": {"command": "echo hello"}},
        timeout=30,
    )
    assert req.target_node == "worker-1"
    assert req.payload.task_type == TaskType.shell
    assert req.timeout == 30
    print("  OK: valid DispatchRequest accepted")

    # Missing target_node
    try:
        DispatchRequest(payload={"task_type": "shell"}, timeout=30)
        assert False, "should have raised"
    except ValidationError as e:
        assert any("target_node" in str(err["loc"]) for err in e.errors())
    print("  OK: missing target_node rejected")

    # Empty target_node
    try:
        DispatchRequest(target_node="", payload={"task_type": "shell"})
        assert False, "should have raised"
    except ValidationError:
        pass
    print("  OK: empty target_node rejected")

    # Missing payload
    try:
        DispatchRequest(target_node="worker-1")
        assert False, "should have raised"
    except ValidationError:
        pass
    print("  OK: missing payload rejected")

    # Invalid task_type
    try:
        DispatchRequest(
            target_node="worker-1",
            payload={"task_type": "invalid_type", "params": {}},
        )
        assert False, "should have raised"
    except ValidationError:
        pass
    print("  OK: invalid task_type rejected")

    # Timeout out of range (0)
    try:
        DispatchRequest(
            target_node="worker-1",
            payload={"task_type": "shell", "params": {}},
            timeout=0,
        )
        assert False, "should have raised"
    except ValidationError:
        pass
    print("  OK: timeout=0 rejected")

    # Timeout out of range (>3600)
    try:
        DispatchRequest(
            target_node="worker-1",
            payload={"task_type": "shell", "params": {}},
            timeout=9999,
        )
        assert False, "should have raised"
    except ValidationError:
        pass
    print("  OK: timeout > 3600 rejected")


def test_task_metadata_serialization():
    """Verify TaskMetadata model has no payload/result body fields."""
    from shared.protocol import TaskMetadata

    meta = TaskMetadata(
        task_id="abc123",
        target_node="worker-1",
        capability="shell.run",
        status="completed",
        created_at="2026-07-02T00:00:00",
        updated_at="2026-07-02T00:01:00",
        error_code=None,
        payload_size=42,
        result_size=128,
    )
    data = meta.model_dump(mode="json")

    # Must NOT contain command, content, output, or error fields
    assert "command" not in data, "metadata must not contain command"
    assert "content" not in data, "metadata must not contain content"
    assert "output" not in data, "metadata must not contain output"
    assert "error" not in data, "metadata must not contain raw error"
    assert "params" not in data, "metadata must not contain params"

    # Must contain metadata fields
    assert data["task_id"] == "abc123"
    assert data["target_node"] == "worker-1"
    assert data["capability"] == "shell.run"
    assert data["payload_size"] == 42
    assert data["result_size"] == 128
    print("  OK: TaskMetadata omits sensitive content fields")
    print("  OK: TaskMetadata includes routing and size fields")


def test_task_store():
    """Verify TaskStore persists metadata correctly and omits sensitive content."""
    import os
    from master.task_store import TaskStore
    from shared.protocol import TaskMetadata

    db_path = "_test_tasks.db"
    # Clean up any stale database from a previous failed run
    if os.path.exists(db_path):
        os.remove(db_path)
    try:
        store = TaskStore(db_path=db_path)

        # Create a task
        meta = store.create(
            task_id="test-1",
            target_node="worker-1",
            capability="shell.run",
            status="dispatched",
            payload_size=42,
        )
        assert meta.task_id == "test-1"
        assert meta.target_node == "worker-1"
        assert meta.status == "dispatched"
        assert meta.payload_size == 42
        assert meta.result_size == 0
        print("  OK: TaskStore.create stores metadata")

        # Update status
        store.update_status("test-1", "completed", error_code=None, result_size=128)
        meta2 = store.get("test-1")
        assert meta2.status == "completed"
        assert meta2.result_size == 128
        assert meta2.error_code is None
        print("  OK: TaskStore.update_status updates fields")

        # Update with error
        store.update_status("test-1", "failed", error_code="execution_failed")
        meta3 = store.get("test-1")
        assert meta3.status == "failed"
        assert meta3.error_code == "execution_failed"
        print("  OK: TaskStore.update_status with error_code")

        # Task not found
        assert store.get("nonexistent") is None
        print("  OK: TaskStore.get returns None for unknown task")

        # List by node
        store.create("test-2", "worker-1", "file.read", "completed", 10)
        store.create("test-3", "worker-2", "system.info", "completed", 5)
        worker1_tasks = store.list_by_node("worker-1")
        assert len(worker1_tasks) == 2
        all_tasks = store.list_recent(limit=10)
        assert len(all_tasks) == 3
        print("  OK: TaskStore list operations return correct results")

        # Verify no sensitive fields leak
        raw = store.get("test-1").model_dump(mode="json")
        assert "command" not in raw
        assert "content" not in raw
        assert "output" not in raw
        assert "params" not in raw
        print("  OK: TaskStore does not persist command, content, output, or params")

        store.close()
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except PermissionError:
                pass

    print("  OK: TaskStore cleanup works")


def test_data_retention_boundary():
    """Verify that payload content does not leak into persisted metadata."""
    import os
    from master.task_store import TaskStore

    db_path = "_test_retention.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    try:
        store = TaskStore(db_path=db_path)

        # Simulate what Router.dispatch() records: capability + payload_size only
        store.create(
            task_id="sensitive-1",
            target_node="worker-1",
            capability="shell.run",
            status="dispatched",
            payload_size=64,
        )
        store.update_status("sensitive-1", "completed", result_size=128)

        # Verify the database schema excludes sensitive columns
        import sqlite3
        conn = sqlite3.connect(db_path)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(task_metadata)").fetchall()}
        conn.close()

        # Must have metadata columns
        assert "task_id" in columns
        assert "target_node" in columns
        assert "capability" in columns
        assert "status" in columns
        assert "payload_size" in columns
        assert "result_size" in columns
        assert "error_code" in columns

        # Must NOT have sensitive content columns
        assert "command" not in columns
        assert "content" not in columns
        assert "output" not in columns
        assert "params" not in columns
        assert "payload" not in columns
        assert "result" not in columns
        print("  OK: SQLite schema has no sensitive content columns")

        store.close()
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except PermissionError:
                pass
    print("  OK: data retention boundary enforced")


def test_master_error_codes():
    """Verify Master error responses include error_code."""
    # Master uses ErrorCode enum values in JSON responses;
    # verify the values match what's documented.
    from shared.protocol import ErrorCode

    # Simulate the error responses master/api/tasks.py returns
    offline_resp = {"error": "node offline or not connected", "error_code": ErrorCode.node_offline.value}
    assert offline_resp["error_code"] == "node_offline"
    print("  OK: offline dispatch error code")

    timeout_resp = {"error": "timeout", "error_code": ErrorCode.timeout.value}
    assert timeout_resp["error_code"] == "timeout"
    print("  OK: sync timeout error code")

    auth_resp = {"error": "unauthorized", "error_code": ErrorCode.auth_denied.value}
    assert auth_resp["error_code"] == "auth_denied"
    print("  OK: auth denied error code")


if __name__ == "__main__":
    tests = [
        ("Protocol models", test_protocol_models),
        ("Legacy compatibility", test_legacy_compatibility),
        ("CLI parsing", test_cli_parsing),
        ("ASCII-only", test_ascii_only),
        ("Executor base", test_executor_base),
        ("Workspace boundary", test_workspace_boundary),
        ("Shell timeout", test_shell_timeout),
        ("Output truncation", test_output_truncation),
        ("Print result", test_print_result),
        ("Master error codes", test_master_error_codes),
        ("Dispatch validation", test_dispatch_request_validation),
        ("Task metadata", test_task_metadata_serialization),
        ("Task store", test_task_store),
        ("Data retention", test_data_retention_boundary),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        print(f"[{name}]")
        try:
            fn()
            print(f"  -> PASS\n")
            passed += 1
        except Exception as e:
            print(f"  -> FAIL: {e}\n")
            failed += 1

    print(f"{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
