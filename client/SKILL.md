# CapOwn Client — Agent Usage Guide

<!-- SPDX-License-Identifier: Apache-2.0 -->

Use this CLI to dispatch tasks to a configured CapOwn worker through the Master API.

## Setup

Create `client/config.ini` from the example and fill:

- `master_url` — the Master HTTPS base URL, for example `https://example.com/gb`
- `client_token` — the client bearer token from Master config

Always choose an explicit online target node for operations. Use `nodes` first.

## Quick Reference

| Task | Command |
|---|---|
| List nodes | `capown nodes` |
| Show system info | `capown info <node>` |
| List directory | `capown ls <node> [path]` |
| Read file | `capown read <node> <path>` |
| Write file | `capown write <node> <path> <content>` |
| Run shell (sync) | `capown run <node> "<command>"` |
| Run shell (async) | `capown dispatch <node> "<command>"` |
| Check task status | `capown task <task_id>` |

### Examples

```bash
capown nodes
capown info worker-1
capown ls worker-1 .
capown read worker-1 /workspace/README.md
capown write worker-1 /workspace/tmp/hello.txt "hello"
capown run worker-1 "pwd && ls -la"
capown dispatch worker-1 "sleep 30 && echo done"
capown task abcdef123456
```

## Agent Decision Flow

1. **Discover** — run `capown nodes` to list registered workers.
2. **Select** — prefer an online node; avoid offline nodes.
3. **Read before write** — use `capown ls` and `capown read` before `capown write`.
4. **Sync for short tasks** — use `capown run` for commands expected to finish quickly.
5. **Async for long tasks** — use `capown dispatch`, then poll with `capown task <task_id>`.
6. **Handle errors**:
   - `workspace_violation` → retry with a workspace-relative path
   - `output_too_large` → narrow the command to produce less output
   - `node_offline` → pick a different node or wait
   - `timeout` → use async dispatch with a longer timeout
   - `auth_denied` → check client_token in config
   - `schema_invalid` → fix the request parameters

## Path Rules

Paths are resolved relative to the worker workspace, normally `/workspace` inside the container.

| You send | Resolves to |
|---|---|
| `project/main.py` | `/workspace/project/main.py` |
| `/workspace/project/main.py` | `/workspace/project/main.py` |
| `../etc/passwd` | denied |

## Legacy Compatibility

Old-style command names are still supported but not recommended:

```bash
python3 client/capown_client.py list_nodes
python3 client/capown_client.py system_info --node worker-1
python3 client/capown_client.py list_directory --node worker-1 .
python3 client/capown_client.py read_file --node worker-1 README.md
python3 client/capown_client.py write_file --node worker-1 tmp/hello.txt "hello"
python3 client/capown_client.py run_command --node worker-1 "pwd && ls -la"
```

## Practices

1. Run `capown nodes` first and always target an explicit online node.
2. Use `capown ls` and `capown read` before `capown write` to understand the target.
3. Check the `error_code` field in results — it tells you what went wrong.
4. For long-running commands, use `capown dispatch` + `capown task` polling.
5. Prefer workspace-relative paths (relative to the worker workspace).
6. All program output is ASCII-only — no emoji, no Unicode decorations.
