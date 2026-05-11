"""Multi-profile YAML config — paths and connection details only.

Secrets (DB passwords) live in the OS keychain, never in this file.
SSH private keys are referenced by path, not embedded.

Default location: <platformdirs.user_config_dir>/opencart-cli/config.yaml
  macOS:   ~/Library/Application Support/opencart-cli/config.yaml
  Linux:   ~/.config/opencart-cli/config.yaml
  Windows: %APPDATA%\\opencart-cli\\config.yaml

Override with env var OPENCART_CLI_CONFIG=/some/path.yaml

Profile shape:
  profiles:
    <name>:
      connection: {type: ssh|ddev|local, ...backend-specific...}
      db: {user, name, host, port}
      opencart: {root, storage, version, table_prefix, admin_path}
      read_only: false
      description: ""
"""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from platformdirs import user_config_dir

from .secrets import get_secret

DEFAULT_OC_VERSION = "3.x"
SUPPORTED_OC_VERSIONS = ("2.x", "3.x", "4.x", "auto")
SUPPORTED_CONNECTION_TYPES = ("ssh", "ddev", "local")

# Sensible defaults for DB host per backend
_DB_HOST_DEFAULTS = {
    "ssh": "localhost",  # DB runs on the remote server, accessed locally there
    "ddev": "db",  # DDEV's conventional service name
    "local": "127.0.0.1",  # Common default for local installs
}


def config_path() -> Path:
    """Resolve the config file path, respecting OPENCART_CLI_CONFIG override."""
    override = os.environ.get("OPENCART_CLI_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path(user_config_dir("opencart-cli", appauthor=False)) / "config.yaml"


def config_dir() -> Path:
    """The directory containing the config file."""
    return config_path().parent


@dataclass
class DBConnection:
    user: str
    name: str
    host: str = "localhost"
    port: int = 3306
    # Password is NOT stored here — resolved from keyring / env at runtime.


@dataclass
class OpenCartInstall:
    root: str  # e.g. /home/user/public_html, or /var/www/html for DDEV
    storage: str = ""  # optional, defaults to <root>/system/storage
    version: str = DEFAULT_OC_VERSION  # "2.x" | "3.x" | "4.x" | "auto"
    table_prefix: str = "oc_"
    admin_path: str = "admin"

    @property
    def effective_storage(self) -> str:
        return self.storage or f"{self.root.rstrip('/')}/system/storage"


@dataclass
class Profile:
    name: str
    connection: dict[str, Any]  # passed to make_connection() at runtime
    db: DBConnection
    opencart: OpenCartInstall
    read_only: bool = False
    description: str = ""

    def db_password(self) -> str | None:
        """Resolve the DB password from env or keyring."""
        return get_secret(
            self.name,
            "db_password",
            env_var=f"OPENCART_{self.name.upper().replace('-', '_')}_DB_PASS",
        )

    @property
    def connection_type(self) -> str:
        return str(self.connection.get("type", "ssh")).lower()

    @property
    def is_read_only(self) -> bool:
        """Auto-readonly for profiles named 'prod*' even if config says otherwise."""
        return self.read_only or self.name.lower().startswith("prod")


@dataclass
class Config:
    default_profile: str = ""
    profiles: dict[str, Profile] = field(default_factory=dict)

    def get_profile(self, name: str | None = None) -> Profile:
        """Resolve the active profile by name, env, or default."""
        candidate = name or os.environ.get("OPENCART_PROFILE") or self.default_profile
        if not candidate:
            if len(self.profiles) == 1:
                return next(iter(self.profiles.values()))
            raise ConfigError(
                "No profile specified and no default set. "
                "Pass --profile <name>, set OPENCART_PROFILE, or run `opencart init`."
            )
        if candidate not in self.profiles:
            available = ", ".join(self.profiles) or "(none — run `opencart init`)"
            raise ConfigError(f"Profile '{candidate}' not found. Available: {available}")
        return self.profiles[candidate]


class ConfigError(Exception):
    """Raised when the config is missing, invalid, or references unknown profiles."""


def load_config(path: Path | None = None) -> Config:
    """Load config from disk. Returns an empty Config if the file doesn't exist."""
    p = path or config_path()
    if not p.exists():
        return Config()

    try:
        raw = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse {p}: {e}") from e

    cfg = Config(default_profile=raw.get("default_profile", ""))
    for name, profile_raw in (raw.get("profiles") or {}).items():
        try:
            cfg.profiles[name] = _parse_profile(name, profile_raw)
        except (KeyError, TypeError, ValueError) as e:
            raise ConfigError(f"Profile '{name}' is malformed: {e}") from e

    return cfg


def save_config(cfg: Config, path: Path | None = None) -> Path:
    """Write config to disk. Creates parent dirs and chmod 600."""
    p = path or config_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    raw: dict = {}
    if cfg.default_profile:
        raw["default_profile"] = cfg.default_profile

    raw["profiles"] = {name: _serialise_profile(prof) for name, prof in cfg.profiles.items()}

    p.write_text(yaml.safe_dump(raw, sort_keys=False, default_flow_style=False))
    try:
        p.chmod(0o600)
    except OSError:
        pass  # Windows or unusual FS — best-effort

    return p


def _parse_profile(name: str, raw: dict) -> Profile:
    conn_raw = raw.get("connection")
    if not conn_raw:
        raise ValueError("missing required 'connection' block")
    conn_type = str(conn_raw.get("type", "")).lower()
    if conn_type not in SUPPORTED_CONNECTION_TYPES:
        raise ValueError(
            f"connection.type must be one of {SUPPORTED_CONNECTION_TYPES}, got {conn_type!r}"
        )

    db_raw = raw.get("db", {})
    oc_raw = raw.get("opencart", {})

    # Default DB host per backend if not specified
    db_host = db_raw.get("host") or _DB_HOST_DEFAULTS.get(conn_type, "localhost")

    return Profile(
        name=name,
        description=raw.get("description", ""),
        read_only=bool(raw.get("read_only", False)),
        connection=deepcopy(conn_raw),
        db=DBConnection(
            user=db_raw["user"],
            name=db_raw["name"],
            host=db_host,
            port=int(db_raw.get("port", 3306)),
        ),
        opencart=OpenCartInstall(
            root=oc_raw.get("root", ""),
            storage=oc_raw.get("storage", ""),
            version=oc_raw.get("version", DEFAULT_OC_VERSION),
            table_prefix=oc_raw.get("table_prefix", "oc_"),
            admin_path=oc_raw.get("admin_path", "admin"),
        ),
    )


def _serialise_profile(p: Profile) -> dict:
    out: dict = {
        "connection": deepcopy(p.connection),
        "db": {
            "user": p.db.user,
            "name": p.db.name,
        },
        "opencart": {
            "root": p.opencart.root,
            "version": p.opencart.version,
            "table_prefix": p.opencart.table_prefix,
        },
    }
    # Only include non-default DB host/port
    default_host = _DB_HOST_DEFAULTS.get(p.connection_type, "localhost")
    if p.db.host != default_host:
        out["db"]["host"] = p.db.host
    if p.db.port != 3306:
        out["db"]["port"] = p.db.port
    if p.opencart.storage:
        out["opencart"]["storage"] = p.opencart.storage
    if p.opencart.admin_path != "admin":
        out["opencart"]["admin_path"] = p.opencart.admin_path
    if p.read_only:
        out["read_only"] = True
    if p.description:
        out["description"] = p.description
    return out
