<p align="center">
  <img src="assets/CapOwn_concept.png" alt="CapOwn Concept" width="800">
</p>

<p align="center">
  <a href="https://github.com/tappat225/CapOwn/stargazers">
    <img src="https://img.shields.io/github/stars/tappat225/CapOwn?style=for-the-badge&color=f1c40f" alt="Stars">
  </a>
  <a href="https://github.com/tappat225/CapOwn/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/license-AGPL--3.0--only%20%2F%20Apache--2.0-blue?style=for-the-badge" alt="License">
  </a>
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/python-%3E%3D3.9-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  </a>
  <a href="https://github.com/tappat225/CapOwn/issues">
    <img src="https://img.shields.io/github/issues/tappat225/CapOwn?style=for-the-badge&color=2ecc71" alt="Issues">
  </a>
  <a href="https://github.com/tappat225/CapOwn/pulls">
    <img src="https://img.shields.io/github/issues-pr/tappat225/CapOwn?style=for-the-badge&color=3498db" alt="Pull Requests">
  </a>
</p>

<h1 align="center">CapOwn</h1>

<p align="center">
  <strong>Multi-host remote operation &amp; AI Agent coordination system</strong><br>
  Dispatch tasks across networks — Workers need only outbound HTTPS, no inbound ports.
</p>

<p align="center">
  <a href="README_zh.md">中文</a>
</p>

---

## ✨ Architecture

A central **Master** node manages and dispatches tasks to multiple **Worker** nodes over HTTPS + SSE, enabling cross-network execution without requiring inbound ports on worker machines.

```
[Client / Agent]
    | (HTTPS POST: dispatch tasks)
    v
[Master (public IP) -- central router]
    ^ (HTTPS POST: report results)
    | (SSE long-poll: push task instructions)
    |
    +-- [Worker @ Node A]
    +-- [Worker @ Node B]
    +-- [Worker @ Node C]
    ...
```

### 🧱 Design Constraints

| Constraint | Description |
|---|---|
| 🔌 **All-outbound** | Workers only need outbound HTTPS. No inbound ports required. |
| 🧭 **Central routing** | All inter-node communication routes through Master. |
| 🧠 **Capability/intelligence split** | Workers provide execution; Agents provide LLM decisions. |
| 🐳 **Dual deployment** | Container (Docker) or host (native). Container mode bind-mounts a host directory; host mode runs commands directly. |

### 🧩 Components

| Component | Role |
|---|---|
| **Master** | Node registry, SSE broker, task router, auth gateway |
| **Worker** | Lightweight daemon — connects to Master, executes tasks, reports results |
| **Client** | CLI tool / SDK to dispatch tasks to Master |

> 📖 See [docs/architecture.md](docs/architecture.md) for the full architecture reference including directory structure.

## 🚀 Quick Deploy (Recommended)

Use the interactive deploy script for a guided setup — no arguments needed:

```bash
cd CapOwn/
python3 deploy.py
```

The deploy script guides you through Master, Worker, or both with interactive prompts.

> 📖 For manual deployment (writing config files, running Docker commands directly), see [docs/deploy.md](docs/deploy.md).

## ⚡ Quick Use

```bash
# List registered workers
python client/capown_client.py nodes

# Run a shell command on a worker
python client/capown_client.py run worker-1 "uname -a"
```

> 📖 See [docs/user_guide.md](docs/user_guide.md) for the full user guide including configuration reference, all CLI commands, direct API usage, error codes, and capability vocabulary.

## 🤝 Contributing

Contributions are welcome! Before opening a pull request, read [CONTRIBUTING.md](CONTRIBUTING.md) and [CLA.md](CLA.md). Pull requests are accepted only from contributors who agree to the CapOwn CLA.

## 📄 License

CapOwn uses an **open-core** licensing model:

| Scope | License |
|---|---|
| `client/`, `worker/`, `shared/`, `docs/`, deployment tooling, root configs | ![Apache-2.0](https://img.shields.io/badge/Apache--2.0-green?style=flat-square) |
| `master/` (Community Master) | ![AGPL-3.0](https://img.shields.io/badge/AGPL--3.0--only-orange?style=flat-square) |
| Commercial Master, hosted service, billing, tenant admin, enterprise | Proprietary |

> 📖 See [LICENSE](LICENSE) for the full repository license notice.
