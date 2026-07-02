# CapOwn — Manual Deployment Guide

<!-- SPDX-License-Identifier: Apache-2.0 -->

> **Tip:** The interactive deploy script (`python3 deploy.py`) is the recommended
> way to deploy. It also supports config-driven and config generation modes:
>
> ```bash
> # Standard interactive deployment
> python3 deploy.py
>
> # Generate a Worker enrollment config
> python3 deploy.py --generate worker --master-url https://master.example.com
>
> # Deploy from an enrollment config (skips role selection)
> python3 deploy.py --config capown-worker.toml
> ```
>
> This guide covers manual setup for advanced use cases.

## Prerequisites

- Docker and Docker Compose installed on the Master host
- Python 3.x available on any Worker host running in host mode
- Outbound HTTPS access from all Worker hosts to the Master

## Master Deployment (Container)

### 1. Write Config File

Create `~/.capown/master/config.toml`:

```toml
[master]
host = "0.0.0.0"
port = "9210"
heartbeat_timeout = "60"
db_path = "/app/data/registry.db"

[auth]
node_token = "<your-node-token>"
client_token = "<your-client-token>"
```

Tokens can be any secure random string. Generate one with:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Prepare Data Directory

```bash
mkdir -p ~/.capown/master/data
```

### 3. Build and Run

```bash
cd master/

# Build with defaults (international mirrors)
DOCKER_BUILDKIT=0 docker compose build

# Or with China mirrors
DOCKER_BUILDKIT=0 \
  APT_MIRROR=mirrors.tuna.tsinghua.edu.cn \
  PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  docker compose build

# Start the container
CAPOWN_MASTER_CONFIG="$HOME/.capown/master/config.toml" \
  CAPOWN_MASTER_DATA="$HOME/.capown/master/data" \
  docker compose up -d

# Check status
docker compose logs master
```

### 4. Verify

```bash
curl http://127.0.0.1:9210/health
```

## Worker Deployment

The Worker control process always runs on the host as a native OS service.
When using the container execution backend, a managed Docker container is
additionally set up for task isolation. The `deploy.py` script handles both
steps automatically.

### Host Execution Backend

Tasks run directly on the host system. Suitable for trusted machines where
Docker is not needed.

#### 1. Write Config File

Create `~/.capown/worker/config.toml`:

```toml
[worker]
execution_mode = "host"
node_id = "<unique-node-name>"
master_url = "https://your-server.com/gb"
workspace = "/"
command_timeout = "120"
reconnect_interval = "5"

[auth]
node_token = "<master-node-token>"
```

#### 2. Install Application Copy

```bash
mkdir -p ~/.capown/worker/app
cp -r ../shared ~/.capown/worker/app/
cp -r ../worker ~/.capown/worker/app/
cp ../worker/requirements.txt ~/.capown/worker/app/
```

#### 3. Create Virtual Environment

```bash
python3 -m venv ~/.capown/worker/venv
~/.capown/worker/venv/bin/pip install -r ~/.capown/worker/app/requirements.txt
```

#### 4. Install systemd Service

Create `~/.config/systemd/user/capown-worker.service`:

```ini
[Unit]
Description=CapOwn Worker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=%h/.capown/worker/venv/bin/python -m worker.daemon
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

Then enable and start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now capown-worker

# Enable linger so the service starts on boot
sudo loginctl enable-linger $USER
```

### Host Execution Backend (Windows)

#### 1. Write Config File

Same as Linux host mode above. Place it at `%USERPROFILE%\.capown\worker\config.toml`.

#### 2. Install Application Copy

```powershell
mkdir "$env:USERPROFILE\.capown\worker\app" -Force
Copy-Item ..\shared "$env:USERPROFILE\.capown\worker\app\" -Recurse
Copy-Item ..\worker "$env:USERPROFILE\.capown\worker\app\" -Recurse
Copy-Item ..\worker\requirements.txt "$env:USERPROFILE\.capown\worker\app\"
```

#### 3. Create Virtual Environment

```powershell
python -m venv "$env:USERPROFILE\.capown\worker\venv"
& "$env:USERPROFILE\.capown\worker\venv\Scripts\pip" install -r "$env:USERPROFILE\.capown\worker\app\requirements.txt"
```

#### 4. Create Scheduled Task

```powershell
# Remove existing task if any
schtasks /Delete /TN CapOwnWorker /F

# Create new task
schtasks /Create `
  /TN CapOwnWorker `
  /SC ONLOGON `
  /TR "$env:USERPROFILE\.capown\worker\venv\Scripts\python -m worker.daemon" `
  /RL LIMITED `
  /F

# Start the task
schtasks /Run /TN CapOwnWorker
```

## Same-machine Master + Worker

When Master and Worker run on the same host, configure the Worker to connect via localhost:

```toml
# worker/config.toml
[worker]
execution_mode = "container"  # or "host"
node_id = "local-worker"
master_url = "http://127.0.0.1:9210"
# ...
```

## Configure Nginx

Merge the following into your HTTPS server block:

```nginx
location /gb/ {
    proxy_pass http://127.0.0.1:9210/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # SSE requires disabled buffering
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;

    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

Then reload: `sudo nginx -t && sudo systemctl reload nginx`

## Security

- **Dual token scheme**: Node Token (worker identity) and Client Token (dispatch authority) are separate
- **All-outbound networking**: Workers never expose inbound ports
- **Path traversal blocked**: All file operations enforce workspace boundary via realpath validation
- **Container isolation**: Both Master and Worker run as non-root in Docker containers
- **Command timeout**: Long-running commands are killed automatically
- **No hardcoded secrets**: Tokens are loaded from local config files or environment overrides
- **Local-only Master port**: Master binds to 127.0.0.1, exposed only via Nginx reverse proxy

## Build System

### Docker build requirements

Two flags are REQUIRED to build on machines where Docker's default bridge network has no DNS resolution (common on cloud VMs):

| Flag | Why |
|---|---|
| `DOCKER_BUILDKIT=0` | BuildKit's `--network=host` does not work reliably; the legacy builder passes host networking through to intermediate containers |
| `--network=host` | Lets the build container use the host's network stack so `apt-get` and `pip` can reach external repos |

### ARG scoping (Dockerfile)

ARGs declared *before* `FROM` are only visible in the `FROM` instruction. To use them in `RUN` steps, re-declare them after `FROM` (without default values):

```dockerfile
ARG APT_MIRROR=deb.debian.org
FROM ${PYTHON_IMAGE}
ARG APT_MIRROR          # re-declare to bring into scope
RUN sed -i "s|http://deb.debian.org|http://${APT_MIRROR}|g" ...
```

### Sudo and environment variables

`sudo` strips most environment variables by default. When running `docker compose build` with `sudo`, env vars like `APT_MIRROR` never reach the docker-compose process. Either:

- Pass them explicitly: `sudo -E env APT_MIRROR=... docker compose build`
- Or build directly with `docker build` and pass `--build-arg`

### Mirror configuration

| Build arg | Default (international) | China example |
|---|---|---|
| `PYTHON_IMAGE` | `python:3.12-slim` | (keep default, Docker Hub works) |
| `APT_MIRROR` | `deb.debian.org` | `mirrors.tuna.tsinghua.edu.cn` |
| `PIP_INDEX_URL` | `https://pypi.org/simple` | `https://pypi.tuna.tsinghua.edu.cn/simple` |

To switch to China mirrors, set the environment variables before building:

```bash
export DOCKER_BUILDKIT=0
export APT_MIRROR=mirrors.tuna.tsinghua.edu.cn
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
docker compose build
```

### Rebuild after code changes

```bash
cd <project-root>
DOCKER_BUILDKIT=0 docker build --no-cache --network=host \
  --build-arg APT_MIRROR=mirrors.tuna.tsinghua.edu.cn \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  -t capown-master -f master/Dockerfile .
cd master/ && docker compose up -d
# Repeat for worker/
```

## Troubleshooting

### Build fails with "Undetermined Error" (apt-get)

The build container cannot reach the Debian repositories. Three fixes:

1. Use `DOCKER_BUILDKIT=0 docker build --network=host` (legacy builder + host network)
2. Use a mirror closer to your server via `--build-arg APT_MIRROR=...`
3. Check that the `APT_MIRROR` build arg is **re-declared after `FROM`** in the Dockerfile (ARG scoping rule)

### Build fails with "deb.debian.org" in logs even though mirror is set

The `--build-arg` value is not reaching the `RUN` instruction. Most likely the ARG is declared before `FROM` but not re-declared inside the stage. See "ARG scoping" in the Build System section above.

### Worker cannot connect to Master

- Verify Master is reachable: `curl <MASTER_URL>/health`
- Check `NODE_TOKEN` matches the Master configuration
- Ensure outbound HTTPS is not blocked by firewall

### Task dispatched but no result / Worker shows no "executing task" log

- Check if the target worker is online: `GET /api/nodes`
- Verify the worker SSE connection is active (Master logs show "broker: node X connected")
- Check worker logs:
  - Container mode: `docker compose logs worker`
  - Linux host mode: `journalctl --user -u capown-worker -f`
  - Windows host mode: `schtasks /Query /TN CapOwnWorker`
- **SSE line-ending mismatch**: `sse-starlette` sends events separated by `\r\n\r\n` (CRLF, per the SSE spec). If the worker splits the stream by `\n\n` (LF only), events will never be parsed. The daemon must use `\r\n\r\n` as the event delimiter, or normalize line endings first.
- **Same-machine worker**: prefer `master_url = "http://127.0.0.1:9210"` to avoid SSE streaming issues through the public IP / NAT path.
- **Blocking HTTP client**: `urllib.request.urlopen().read()` may hang indefinitely on SSE streams served by uvicorn. Use an async HTTP client (`httpx`, `aiohttp`) with streaming support instead.
