# agent.md — CapOwn Programming Guide

<!-- SPDX-License-Identifier: Apache-2.0 -->

> This file provides project-level context and rules for AI coding assistants (Claude, Copilot, etc.).

## Project Overview

CapOwn is a distributed multi-host remote operation and AI Agent coordination system. A central Master node manages multiple Worker nodes over HTTPS + SSE, enabling cross-network task execution.

| Component | Directory | Description |
|---|---|---|
| Shared | `shared/` | Protocol definitions, auth utilities, config schemas |
| Master | `master/` | Central control plane (Starlette + SSE + SQLite) |
| Worker | `worker/` | Execution daemon with pluggable executors |
| MCP Server (legacy) | `server/` | Single-node FastMCP + Docker |
| MCP Server (legacy) | `server/` | Single-node FastMCP + Docker |
| CLI Client (legacy) | `client/` | Command-line client + persistent session daemon |

## Rules

### 0. Structured Error Codes

Task results carry machine-readable error codes alongside human messages:

| Code | Meaning |
|---|---|
| `node_offline` | Target worker is not connected |
| `auth_denied` | Token missing or invalid |
| `capability_not_found` | Task type not supported by worker |
| `schema_invalid` | Request body failed validation |
| `workspace_violation` | Path resolved outside workspace boundary |
| `timeout` | Command or sync-wait exceeded deadline |
| `output_too_large` | Result output exceeded `max_output_size` |
| `execution_failed` | Generic execution error |
| `worker_unhealthy` | Worker reported unhealthy state |
| `rate_limited` | Too many requests |

The `TaskResult` model includes `error_code: Optional[str]` and `truncated: bool` fields.

### 0.1 Capability Vocabulary

Product-facing capability names (used in CLI and registration):

| Capability | Task Type | Description |
|---|---|---|
| `system.info` | `system_info` | Host OS and resource info |
| `file.list` | `list_dir` | List directory contents |
| `file.read` | `file_read` | Read file content |
| `file.write` | `file_write` | Write content to file |
| `shell.run` | `shell` | Execute shell command |

The `Capability` enum and mapping tables are in `shared/protocol.py`.

### 0.2 CLI Commands

| Command | Legacy Alias | Description |
|---|---|---|
| `capown nodes` | `list_nodes` | List registered workers |
| `capown run <node> <cmd>` | `run_command` | Execute shell command (sync) |
| `capown read <node> <path>` | `read_file` | Read a file |
| `capown write <node> <path> <content>` | `write_file` | Write content to a file |
| `capown ls <node> [path]` | `list_directory` | List directory contents |
| `capown info <node>` | `system_info` | Show system information |
| `capown dispatch <node> <cmd>` | — | Execute shell command asynchronously, returns task_id |
| `capown task <task_id>` | — | Show task status and metadata by task_id |

Old command names remain usable for backward compatibility.

### 0.3 API Input Validation

Task dispatch endpoints (`/api/tasks/dispatch`, `/api/tasks/dispatch_sync`) validate
request bodies using Pydantic's `DispatchRequest` model:

- `target_node` — required, must be non-empty string
- `payload` — required, must contain valid `task_type` from `TaskType` enum
- `timeout` — optional, integer 1–3600 (default 120)

Invalid requests return HTTP 400 with `error_code: schema_invalid` and
a human-readable error message. JSON parse errors also return `schema_invalid`.

### 0.4 Task Metadata Persistence

The Master persists minimal task metadata in a separate SQLite database (`tasks.db`).
Only routing and status fields are stored — never command text, file content,
or full stdout/stderr.

**Stored:** task_id, target_node, capability, status, created_at, updated_at,
error_code, payload_size, result_size.

**Not stored:** command text, file content, stdout/stderr, payload body.

`GET /api/tasks/{task_id}` returns metadata by default. Pass `?full=true`
to include the result body (if still available in the in-memory cache).

### 0.5 Output Size Limit

Worker config `max_output_size` (env: `MAX_OUTPUT_SIZE`) caps result output
at 200,000 bytes by default. Exceeding this returns `output_too_large` with an
empty output and truncated flag set.

Truncation is applied centrally in the worker daemon (`_truncate`) — executors
no longer hardcode their own slice limits, so the configured maximum is always
authoritative.

### 1. Default Language — English Only

All project content must be in English, including code (names, comments, docstrings), commit messages, program output, and log messages.

**Exception:** Documentation and README files may use other languages. End-user-facing UI strings may also use other languages when localization is explicitly required.

### 2. No Special Characters in Program Output

All program output (including `print()`, log messages, tool return strings, CLI output) **must NOT contain**:

- Emoji characters
- Unicode box-drawing or decorative characters
- ANSI escape sequences
- Fullwidth symbols or special Unicode punctuation
- Non-ASCII quotes, dashes, or ellipses

**Allowed character set:** ASCII printable characters only (0x20-0x7E).

### 3. No Hardcoded Secrets

- Tokens, keys, URLs, and domain names **must never** be hardcoded in source code
- Load application configuration through the project config loaders
- Environment variables may override file-based configuration for deployment and secrets
- Provide `config.toml.example` or `config.ini.example` template files with `<your-xxx>` placeholders
- Real config files must be listed in `.gitignore`

### 4. Configuration File Pattern

```
Real config (gitignored)     Template (committed)
------------------------     --------------------
master/config.toml           master/config.toml.example
worker/config.toml           worker/config.toml.example
client/config.ini            client/config.ini.example
```

When modifying configuration: update the matching `.example` template first, then inform the user to sync their local real config.

### 5. Directory Structure and Separation

See [docs/architecture.md](docs/architecture.md) for the full directory layout.

Cross-directory imports must go through `shared/`. Master and Worker must not import from each other directly.

- `shared/` — protocol models, auth utilities, config schemas
- `master/` — control plane
- `worker/` — execution plane
- `server/` — legacy single-node MCP server
- `client/` — legacy CLI client

### 6. Protocol and Data Models

- All inter-service data structures are defined in `shared/protocol.py` using Pydantic
- Use `model_dump(mode="json")` for serialization
- Task types are enumerated in `TaskType`; node/task statuses in `NodeStatus`/`TaskStatus`
- New task types require adding to the enum and implementing a corresponding executor

### 7. Executor Pattern (Worker)

- All executors inherit from `worker/executor/base.py:BaseExecutor`
- Implement `async execute(self, params: dict) -> ExecResult`
- ExecResult has: `success: bool`, `output: str`, `error: str`
- New executors are registered in `worker/daemon.py:_handle_task()`

### 8. API Authentication

- Two token types: `NODE_TOKEN` (workers) and `CLIENT_TOKEN` (clients/agents)
- Node endpoints (`/api/nodes/*`, `/api/events`, `/api/tasks/result`) require Node Token
- Client endpoints (`/api/tasks/dispatch*`) require Client Token
- Tokens are passed as `Authorization: Bearer <token>` headers

### 9. SSE Communication

- Workers connect to `GET /api/events?node_id=X` with Node Token
- Master pushes task events as SSE with `event: task` and JSON data
- Master sends `event: ping` every 30s to keep connections alive
- Workers must handle reconnection on connection loss

### 10. Path Security

- **Container mode**: filesystem isolation is provided by Docker namespace boundaries
- **Host mode**: the worker has full host filesystem access; security is enforced
  at the tool-calling / Master layer rather than at the filesystem level
- **Workspace boundary enforcement**: all file and shell executors resolve paths
  against the configured workspace and reject paths that escape it, returning
  `workspace_violation` error code. Path traversal (`../../`) is blocked at the
  executor level for read, write, list, and shell cwd operations.
- Worker workspace is configured by `worker.workspace` or the `WORKSPACE_DIR`
  override. In container mode it defaults to `/workspace`; in host mode to `/`.
- The Docker host directory mounted at `/workspace` is controlled by
  `CAPOWN_HOST_WORKSPACE`

### 11. Error Handling

- Executors return `ExecResult(success=False, error="...")` on failure — never raise
- Master API returns JSON error responses with appropriate HTTP status codes
- Worker reports failures via Reporter with `TaskStatus.failed`
- Shell commands have timeout protection via `asyncio.wait_for`

### 12. Python Code Style

- Use `asyncio` async patterns throughout master and worker
- Module-level constants: `UPPER_CASE`
- Function names: `snake_case`
- Import order: standard library -> third-party -> local modules
- Type hints on function signatures
- Pydantic models for all protocol data structures
- Dataclasses for configuration

### 13. Git Commits

- Commit messages must be in English, using a concise imperative style
- Example: `Add task dispatch endpoint to master API`
- Before committing, verify no sensitive files (.env, real config files, real tokens) are included

### 14. Docker Build

- **ARG scoping**: ARGs declared before `FROM` are only visible to the
  `FROM` instruction. To use them in `RUN` steps, re-declare them after
  `FROM` (without default values).
- **Build network**: Some cloud VMs have no DNS on Docker's default bridge.
  Use `DOCKER_BUILDKIT=0 docker build --network=host` to let build
  containers use the host network stack.
- **International mirrors**: Dockerfiles accept `APT_MIRROR` and
  `PIP_INDEX_URL` build args. Defaults are international (deb.debian.org,
  pypi.org). For China deployments, pass
  `APT_MIRROR=mirrors.tuna.tsinghua.edu.cn` and
  `PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple`.
- **No `.env` files**: Mirror configuration goes through docker-compose
  build args with environment variable overrides, not `.env` files.

### 15. SSE Implementation

- `sse-starlette` sends SSE events separated by `\r\n\r\n` (CRLF), per the
  SSE spec. Worker daemons must split the byte stream by `\r\n\r\n`, NOT
  `\n\n`.
- Workers must use an async HTTP client (`httpx`, `aiohttp`) for SSE
  streaming. Synchronous `urllib` may hang on uvicorn-served chunked
  responses.
- Master SSE endpoint (`/api/events?node_id=X`) requires Node Token auth.
  It uses server-sent events with `event: task` and `event: ping` types.
- Nginx must have `proxy_buffering off`, `proxy_cache off`, and long
  timeouts (`proxy_read_timeout 3600s`) for the SSE location block.

### 16. Workspace

- The workspace setting is a base directory for resolving relative task
  paths — it is not a security boundary.
- In **container mode**, Worker `config.toml` must use the container path
  (`/workspace`) for the workspace setting — NOT the host path. The
  user-selected host workspace is bind-mounted into that container path.
  Docker provides real filesystem isolation.
- In **host mode**, workspace is set to `/` (full host filesystem access).
  Security is enforced at the Master / tool-calling layer.
- `CAPOWN_HOST_WORKSPACE` (env) controls which host directory is
  mounted to `/workspace` in the worker container (container mode only).

### 17. Deployment

- `deploy.py` is the single entry point for interactive deployment (menu-driven, zero CLI arguments).
- For manual deployment, config file reference, and Docker command details, see [docs/deploy.md](docs/deploy.md).
- Config directory `~/.capown/` is the canonical home for all persistent deployment data. Docker containers mount config and data paths from there via environment variables.

### 18. License and Contribution Boundaries

- External contributions require agreement to the CapOwn CLA in `CLA.md`.
- Preserve SPDX identifiers on new and modified files.
- Files under `master/` are AGPL-3.0-only unless a file explicitly says
  otherwise.
- Files under `client/`, `worker/`, `shared/`, `docs/`, tests, deployment
  tooling, and root-level project files are Apache-2.0 unless a file
  explicitly says otherwise.
- Shared code used by both open source and commercial components should live
  under `shared/` with Apache-2.0 licensing.
- Proprietary or commercial components must not copy implementation code from
  the AGPL-licensed `master/` tree unless the maintainer has intentionally
  handled the AGPL licensing implications.

### 19. Config-Driven Deploy

`deploy.py --config <path>` loads an enrollment config TOML file to skip
interactive role selection and pre-fill deployment parameters.

- `role` is required and must be `master`, `worker`, or `client`.
- Worker config requires `master_url`, `node_token`, and `node_id`.
- Client config requires `master_url` and `client_token`.
- Mirror selection is only asked when not present in config.
- A full parameter review panel is shown before deployment.
- Existing `python deploy.py` (no `--config`) is unchanged.

### 20. Worker Execution Mode Naming

The Worker differentiates between the **control process location** (always
host-resident) and the **task execution backend** (`host` or `container`).

- Config key: `worker.execution_mode` (primary), falls back to legacy `mode`.
- Environment variable: `EXECUTION_MODE` (primary), falls back to `WORKER_MODE`.
- The protocol registration field is still named `mode` for backward
  compatibility.
- Old configs with `mode = "host"` or `mode = "container"` continue to work.

### 21. Execution Backend Abstraction

The Worker uses a pluggable execution backend to decouple task execution from
the deployment model. The backend is selected at startup by `execution_mode`.

| Backend | Class | File | Description |
|---|---|---|---|
| Host | `HostExecutionBackend` | `worker/execution/host.py` | Tasks run natively on the host |
| Docker | `DockerExecutionBackend` | `worker/execution/docker.py` | Tasks run via `docker exec` |

- Backend interface: `run_shell`, `read_file`, `write_file`, `list_dir`, `system_info`.
- Factory entry: `worker/execution/__init__.py:create_backend()`.
- The worker daemon creates the backend at startup and delegates all
  `_handle_task` calls to it.
- Workspace boundary enforcement is shared through
  `ExecutionBackend._resolve_workspace_path()`.
- Output truncation remains centralized in the daemon's `_truncate()`.
- `WorkerDaemon._handle_task()` routes through the backend regardless of
  execution mode.

### 22. Worker Deployment Model

The Worker control process always runs on the host as a native OS service.
Docker is used only as the task execution backend when
`execution_mode = "container"`.

- `_deploy_worker_host()` deploys a host-resident Worker service (Linux
  systemd or Windows scheduled task).
- `_deploy_worker_container()` deploys a host-resident Worker service PLUS
  a managed Docker execution container.
- The managed execution container (`capown-worker-exec`) is built from
  `worker/execution.Dockerfile` and stays alive with `tail -f /dev/null`.
- Default execution mode is `container`.
- Default host workspace is `$HOME/.capown/workspace`.
- Default container workspace is `/workspace`.
- Managed execution container mounts host workspace at container workspace.

### 23. Config Generation

`deploy.py --generate <role>` creates a role-specific enrollment config file
without performing deployment.

```bash
# Generate a Worker enrollment config
python deploy.py --generate worker --master-url https://master.example.com

# Generate a Client enrollment config
python deploy.py --generate client --master-url https://master.example.com
```

- `--generate worker` prompts for Node ID (or `--node-id`) and generates a
  node token, execution mode and workspace defaults.
- `--generate client` prompts for client token generation.
- `--master-url` and `--node-id` can be passed as CLI arguments to skip prompts.
- Generated configs never include local machine paths (uses `workspace_preset`).
- Tokens are masked in preview output.
- Generated configs contain authentication tokens; store and transfer securely.
