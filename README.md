# CapOwn

<p align="center">
  <img src="assets/CapOwn_readme_hero.png" alt="CapOwn architecture: AI Agent connects through Master to outbound-only Workers" width="100%">
</p>

----

<p align="center">
[ <b>En</b> | <a href="README_zh.md">中</a> ]
<b>Multi-host remote operation and AI Agent coordination.</b>
</p>

[![License](https://img.shields.io/badge/license-AGPL--3.0--only%20%2F%20Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.9-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Issues](https://img.shields.io/github/issues/tappat225/CapOwn)](https://github.com/tappat225/CapOwn/issues)
[![Pull requests](https://img.shields.io/github/issues-pr/tappat225/CapOwn)](https://github.com/tappat225/CapOwn/pulls)

CapOwn lets a local AI Agent use other machines as remote execution hands.
Workers keep an outbound HTTPS/SSE connection to a Master, so machines behind
NAT do not need public IPs or inbound ports.

**One Agent. Many devices. No inbound ports. Minimal-trust relay.**

[User guide](docs/user_guide.md) | [Deployment guide](docs/deploy.md) | [Contributing](CONTRIBUTING.md)

## Why CapOwn

Modern AI coding agents often know what to do, but the right machine is
somewhere else: a Linux test box behind NAT, a workstation with a GPU, a NAS, or
a desktop with local-only tools.

CapOwn focuses on a narrow first job:

- install a lightweight Worker on another machine;
- let a local Agent discover it;
- run file, shell, and system information tasks through a Master relay;
- get structured results and machine-readable errors back.

## Features

- **Outbound-only workers**: Workers connect to Master over HTTPS + SSE.
- **Agent-friendly actions**: shell, file read/write/list, and system info.
- **Compact capability vocabulary**: `shell.run`, `file.read`, `file.write`,
  `file.list`, and `system.info`.
- **Structured errors**: machine-readable codes such as `node_offline`,
  `workspace_violation`, `timeout`, and `output_too_large`.
- **Workspace controls**: file and shell operations are resolved against the
  configured Worker workspace.
- **Sync and async tasks**: use short synchronous calls or dispatch longer tasks
  and poll task metadata.
- **Minimal task persistence**: Master stores routing/status metadata, not raw
  commands, file contents, or full stdout/stderr.
- **Container or host Worker mode**: use Docker isolation or trusted native host
  execution.

## Quick Start

Use the interactive deployment script:

```bash
git clone https://github.com/tappat225/CapOwn.git
cd CapOwn
python3 deploy.py
```

Then configure the client from `client/config.ini.example`.

The CapOwn client is designed for **AI Agents**. After configuration, direct your
AI Agent to read [client/SKILL.md](client/SKILL.md) — the agent uses the `capown`
commands to discover workers, run shell commands, read and write files.

You can also verify the connection manually:

```bash
python client/capown_client.py nodes
python client/capown_client.py info worker-1
python client/capown_client.py run worker-1 "echo hello"
```

For long-running tasks (`capown dispatch` + `capown task`), direct API calls,
error codes, and capability vocabulary, see
[docs/user_guide.md](docs/user_guide.md) and
[client/SKILL.md](client/SKILL.md).

## Architecture

```text
AI Agent / CLI
    |
    | HTTPS task dispatch
    v
CapOwn Master
    |
    | SSE task events over outbound Worker connection
    v
CapOwn Worker
    |
    | local execution
    v
Target device workspace
```

### Components

| Component | Directory | Role |
|---|---|---|
| Shared | `shared/` | Protocol models, auth helpers, config schemas |
| Master | `master/` | Starlette control plane, registry, router, SSE broker |
| Worker | `worker/` | Lightweight daemon and executors |
| Client | `client/` | CLI and Agent-facing usage guide |
| Docs | `docs/` | Deployment and user documentation |

## CLI

| Command | Description |
|---|---|
| `capown nodes` | List registered workers |
| `capown info <node>` | Show worker system information |
| `capown ls <node> [path]` | List files inside the worker workspace |
| `capown read <node> <path>` | Read a file |
| `capown write <node> <path> <content>` | Write a file |
| `capown run <node> <command>` | Run a shell command |
| `capown dispatch <node> <command>` | Dispatch an async shell task |
| `capown task <task_id>` | Poll task metadata |

Legacy command names remain available for backward compatibility.

## Documentation

- [User guide](docs/user_guide.md): client config, CLI commands, direct API
  calls, error codes, and data retention.
- [Deployment guide](docs/deploy.md): Docker, host mode Worker deployment,
  Nginx/SSE proxy notes, and troubleshooting.
- [CapOwn Agent Skill](client/SKILL.md): guidance for AI Agents using CapOwn.

## Security Model

CapOwn is a remote execution tool for machines you control.

- Node and client APIs use separate bearer tokens.
- Worker filesystem operations are resolved against a configured workspace.
- Container mode relies on Docker namespace boundaries.
- Host mode runs commands on the host and should be used only on trusted
  machines.
- The open-source Master persists only task metadata by default.

See [docs/user_guide.md](docs/user_guide.md#data-retention) for data retention
details.

## Contributing

Contributions are welcome. Before opening a pull request, read
[CONTRIBUTING.md](CONTRIBUTING.md) and [CLA.md](CLA.md). Pull requests are
accepted only from contributors who agree to the CapOwn CLA.

## License

CapOwn uses an open-core licensing model.

| Scope | License |
|---|---|
| `client/`, `worker/`, `shared/`, `docs/`, tests, deployment tooling, root project files | Apache-2.0 |
| `master/` | AGPL-3.0-only |
| Commercial Master, hosted service, billing, tenant admin, enterprise features | Proprietary |

See [LICENSE](LICENSE) and the files under [LICENSES](LICENSES/) for details.
