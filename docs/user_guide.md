# CapOwn — User Guide

<!-- SPDX-License-Identifier: Apache-2.0 -->

## Configuration

Configuration is loaded from local files by default. Environment variables are supported as an override layer for container orchestration and secret injection.

Load order:

```text
environment variables > configuration file > defaults
```

### Master (`master/config.toml`)

| TOML key | Env override | Default | Description |
|---|---|---|---|
| `master.host` | `MASTER_HOST` | `0.0.0.0` | Bind address |
| `master.port` | `MASTER_PORT` | `9210` | Listen port |
| `auth.node_token` | `NODE_TOKEN` | (required) | Token for worker authentication |
| `auth.client_token` | `CLIENT_TOKEN` | (required) | Token for client/agent authentication |
| `master.heartbeat_timeout` | `HEARTBEAT_TIMEOUT` | `60` | Seconds before marking node offline |
| `master.db_path` | `MASTER_DB` | `/app/data/registry.db` | SQLite database path (container-side) |

The Master container reads `/etc/capown/master.toml` at runtime. The Compose file mounts the host config and data directories from `~/.capown/master/` into the container (paths are set via `CAPOWN_MASTER_CONFIG` and `CAPOWN_MASTER_DATA` environment variables).

### Worker (`worker/config.toml`)

| TOML key | Env override | Default | Description |
|---|---|---|---|
| `worker.execution_mode` | `EXECUTION_MODE` | `container` | Task execution backend: `"host"` or `"container"`. Falls back to legacy `mode` / `WORKER_MODE` if not set. |
| `worker.node_id` | `NODE_ID` | (required) | Unique identifier for this worker |
| `worker.master_url` | `MASTER_URL` | `https://localhost:9210` | Master endpoint URL |
| `auth.node_token` | `NODE_TOKEN` | (required) | Authentication token (must match Master) |
| `worker.workspace` | `WORKSPACE_DIR` | `/workspace` | Workspace path (container: `/workspace`; host: `~/.capown/workspace`) |
| `worker.command_timeout` | `COMMAND_TIMEOUT` | `120` | Shell command timeout in seconds |
| `worker.max_output_size` | `MAX_OUTPUT_SIZE` | `200000` | Maximum result output bytes before truncation |
| `worker.reconnect_interval` | `RECONNECT_INTERVAL` | `5` | Seconds between reconnect attempts |

Config file locations (resolved in order of priority):

1. `$CAPOWN_CONFIG` environment variable
2. `~/.capown/worker/config.toml` (host execution backend default)
3. `/etc/capown/worker.toml` (container execution backend default)
4. `worker/config.toml` (dev mode fallback)

The Worker control process always runs on the host as a native OS service,
regardless of execution mode. In container execution backend mode (`execution_mode
= "container"`), the deploy script additionally sets up a managed Docker execution
container. The worker daemon uses `docker exec` internally to run tasks inside
that container. In host execution backend mode (`execution_mode = "host"`), tasks
run directly on the host.

The deploy script installs a stable application copy under `~/.capown/worker/app`
and runs it through `~/.capown/worker/venv`. This keeps the deployed worker
independent from the source checkout path after deployment.

### Client (`client/config.ini`)

The client uses INI so it can run on older Python versions without installing extra dependencies. It automatically reads `client/config.ini`, or a custom path passed with `--config` / `CAPOWN_CLIENT_CONFIG`.

| INI key | Env override | Default | Description |
|---|---|---|---|
| `client.master_url` | `MASTER_URL` | `https://<your-domain>/gb` | Master API base URL |
| `client.client_token` | `CLIENT_TOKEN` | (required) | Client bearer token |
| `client.timeout` | `CLIENT_TIMEOUT` | `120` | Synchronous task timeout in seconds |

The client intentionally has no default node. Run `nodes` and pass `<node-id>` on every worker operation.

### Client Config Discovery

The client automatically searches for its config in the following order:

1. `$CAPOWN_CLIENT_CONFIG` environment variable
2. `client/config.ini` (alongside the script)
3. `./client/config.ini` (current working directory)
4. `~/.config/capown/client.ini`
5. `~/.capown/client/config.ini` (written by `deploy.py --generate client`)

## Config-Driven Deployment

CapOwn supports non-interactive deployment via enrollment config files. The
Master operator can generate role-specific configs, then hand them to target
machine operators.

### Generate an Enrollment Config

On the Master machine (or any trusted machine):

```bash
# Generate a Worker enrollment config
python3 deploy.py --generate worker --master-url https://master.example.com

# Generate a Client enrollment config
python3 deploy.py --generate client --master-url https://master.example.com
```

The command prompts for additional fields (Node ID, output path) unless
provided via `--node-id` and `--output`. Tokens are generated automatically
and masked in the preview. The generated file contains top-level keys and
role-specific sections in TOML format.

### Deploy from an Enrollment Config

On the target machine, transfer the generated config file and run:

```bash
# Deploy Worker from config (skips role selection)
python3 deploy.py --config capown-worker.toml

# Deploy Client from config
python3 deploy.py --config capown-client.toml
```

The deploy script:
1. Reads the `role` field from the config.
2. Skips the interactive role selection step.
3. Asks for mirror selection only if not specified in the config.
4. Resolves local defaults (e.g., `workspace_preset = "user_home"` resolves
   to `$HOME/.capown/workspace`).
5. Shows a complete parameter review panel.
6. Proceeds only after explicit user confirmation.

### Enrollment Config Format

Worker:
```toml
role = "worker"
master_url = "https://master.example.com"
node_id = "worker-example"
node_token = "<your-node-token>"

[worker]
execution_mode = "container"
workspace_preset = "user_home"
workspace_relative = ".capown/workspace"
container_workspace = "/workspace"

[deploy]
mirror = "default"  # "default" or "china"
```

Client:
```toml
role = "client"
master_url = "https://master.example.com"
client_token = "<your-client-token>"

[deploy]
mirror = "default"  # "default" or "china"
```

## CLI Usage

```bash
# List registered workers
python client/capown_client.py nodes

# Run a shell command (synchronous, waits for result)
python client/capown_client.py run worker-1 "uname -a"

# Read a file
python client/capown_client.py read worker-1 /etc/hostname

# List directory contents
python client/capown_client.py ls worker-1 /tmp

# Get system info
python client/capown_client.py info worker-1

# Dispatch a long-running command (async, returns task_id)
python client/capown_client.py dispatch worker-1 "sleep 30 && echo done"

# Check task status by task_id
python client/capown_client.py task <task_id>
```

Legacy command names are also supported for backward compatibility:

```bash
python client/capown_client.py list_nodes
python client/capown_client.py run_command --node worker-1 "uptime"
python client/capown_client.py system_info --node worker-1
```

## Direct API Usage

Tasks can also be dispatched directly via curl:

```bash
# Via nginx proxy (external clients):
curl -X POST https://<master-domain>/gb/api/tasks/dispatch \
  -H "Authorization: Bearer <client-token>" \
  -H "Content-Type: application/json" \
  -d '{"target_node": "worker-1", "payload": {"task_type": "shell", "params": {"command": "uname -a"}}}'

# Or direct to Master port (local):
curl -X POST http://127.0.0.1:9210/api/tasks/dispatch \
  -H "Authorization: Bearer <client-token>" \
  -H "Content-Type: application/json" \
  -d '{"target_node": "worker-1", "payload": {"task_type": "shell", "params": {"command": "uname -a"}}}'
```

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/nodes/register` | Node Token | Register a worker node |
| POST | `/api/nodes/heartbeat` | Node Token | Update node heartbeat |
| GET | `/api/nodes` | - | List all registered nodes |
| GET | `/api/events?node_id=X` | Node Token | SSE event stream for a worker |
| POST | `/api/tasks/dispatch` | Client Token | Dispatch task (async) |
| POST | `/api/tasks/dispatch_sync` | Client Token | Dispatch and wait for result |
| POST | `/api/tasks/result` | Node Token | Worker reports task result |
| GET | `/api/tasks/{task_id}` | - | Get task metadata (add `?full=true` for result body) |
| GET | `/health` | - | Health check |

## Data Retention

The Master stores only minimal task metadata in its database:

**Persisted to SQLite:** task_id, target_node, capability, status, timestamps,
error_code, payload_size, result_size.

**Not persisted:** command text, file content, stdout/stderr, task payload body.

Synchronous task results (`dispatch_sync`) are kept in an in-memory cache for
the duration of the wait, then remain available for retrieval until the Master
process restarts. Asynchronous task metadata is persisted and survives restarts.
Pass `?full=true` to `GET /api/tasks/{task_id}` to retrieve the in-memory result
body (if still available).

## Structured Error Codes

Task results include machine-readable error codes for programmatic handling:

| Code | Meaning |
|---|---|
| `node_offline` | Target worker is not connected to Master |
| `auth_denied` | Bearer token missing or does not match |
| `capability_not_found` | Worker does not support the requested task type |
| `schema_invalid` | Request body failed validation |
| `workspace_violation` | File path resolved outside the configured workspace boundary |
| `timeout` | Command or sync-wait exceeded the configured deadline |
| `output_too_large` | Result output exceeded `max_output_size`; output is empty |
| `execution_failed` | Generic execution failure (check `error` field) |
| `worker_unhealthy` | Worker reported an unhealthy state |
| `rate_limited` | Too many requests (not yet enforced) |

The `error_code` field is `null`/absent when the task succeeds. The `truncated` boolean flag is `true` when output was capped due to size limits.

## Capability Vocabulary

Workers advertise their capabilities as compact strings. The product-facing names are mapped to internal task types:

| Capability | Task Type | Description |
|---|---|---|
| `system.info` | `system_info` | Host OS, release, memory info |
| `file.list` | `list_dir` | List directory contents |
| `file.read` | `file_read` | Read file content |
| `file.write` | `file_write` | Write content to file |
| `shell.run` | `shell` | Execute a shell command |

Capabilities appear in the `capown nodes` listing and are used by Agents to select an appropriate worker for a task.
