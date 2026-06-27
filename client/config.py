"""INI configuration loader for the WorkBridge client."""

import configparser
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ClientConfig:
    mcp_url: str = "https://<your-domain>/_mcp"
    auth_token: str = ""
    socket_path: str = "/tmp/mcp-daemon.sock"
    pid_file: str = "/tmp/mcp-daemon.pid"


def _env(name, fallback):
    value = os.environ.get(name)
    return fallback if value is None or value == "" else value


def _candidate_paths():
    env_path = os.environ.get("WORKBRIDGE_CLIENT_CONFIG")
    if env_path:
        yield Path(env_path).expanduser()

    yield Path(__file__).with_name("config.ini")
    yield Path.cwd() / "client" / "config.ini"
    yield Path.home() / ".config" / "workbridge" / "client.ini"


def _read_ini(path):
    parser = configparser.ConfigParser()
    if path and Path(path).expanduser().exists():
        parser.read(str(Path(path).expanduser()))
    return parser


def load_client_config(path=None):
    config_path = Path(path).expanduser() if path else next(
        (candidate for candidate in _candidate_paths() if candidate.exists()),
        None,
    )
    parser = _read_ini(config_path)
    section = parser["client"] if parser.has_section("client") else {}

    return ClientConfig(
        mcp_url=_env("MCP_URL", section.get("mcp_url", ClientConfig.mcp_url)),
        auth_token=_env("AUTH_TOKEN", section.get("auth_token", ClientConfig.auth_token)),
        socket_path=_env("MCP_SOCKET_PATH", section.get("socket_path", ClientConfig.socket_path)),
        pid_file=_env("MCP_PID_FILE", section.get("pid_file", ClientConfig.pid_file)),
    )
