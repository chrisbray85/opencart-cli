"""Pluggable connection backends — SSH, DDEV, or local subprocess.

The CLI doesn't care HOW we reach the OpenCart install, only that it can:
  - run a PHP snippet and capture stdout
  - run a shell command and capture stdout/stderr
  - read and write files

Three backends ship in v1.0:
  - SSHConnection    — paramiko over SSH (remote VPS)
  - DDEVConnection   — `ddev exec` (local DDEV development)
  - LocalConnection  — direct subprocess (local PHP install, Docker Compose, MAMP)

Adding a new backend = subclass Connection and register it in `make_connection`.
"""

from __future__ import annotations

import base64
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import paramiko

# ---------- Backend config dataclasses ----------


@dataclass
class SSHConfig:
    host: str
    user: str
    key: str = "~/.ssh/id_ed25519"
    port: int = 22

    @property
    def key_path(self) -> Path:
        return Path(self.key).expanduser()


@dataclass
class DDEVConfig:
    project_path: str  # local directory where `ddev` commands run
    php_bin: str = "ddev exec php"  # override only if your DDEV is non-standard

    @property
    def project_dir(self) -> Path:
        return Path(self.project_path).expanduser()


@dataclass
class LocalConfig:
    php_bin: str = "php"  # e.g. "docker compose exec web php" for Docker setups
    cwd: str = ""  # working directory; empty = current shell cwd


# ---------- Abstract base ----------


class Connection(ABC):
    """Polymorphic execution surface used by `OpenCartDB`."""

    @abstractmethod
    def exec_php_stdin(self, php_code: str, timeout: int = 60) -> str:
        """Pipe PHP code to a PHP process on the target, return stdout."""

    @abstractmethod
    def exec_command(self, command: str, timeout: int = 30) -> tuple[str, str]:
        """Run a shell command on the target, return (stdout, stderr)."""

    @abstractmethod
    def read_file(self, remote_path: str, max_bytes: int = 1_000_000) -> str:
        """Read a file on the target, capped at max_bytes."""

    @abstractmethod
    def write_file(self, remote_path: str, content: str) -> None:
        """Write to a file on the target."""

    def close(self) -> None:
        """Tear down the connection. No-op by default; override if needed."""


# ---------- SSH ----------


class SSHConnection(Connection):
    """paramiko-backed SSH connection with helpful error messages."""

    def __init__(self, cfg: SSHConfig):
        self.cfg = cfg
        self._client: paramiko.SSHClient | None = None

    def _client_(self) -> paramiko.SSHClient:
        if self._client is not None:
            t = self._client.get_transport()
            if t is not None and t.is_active():
                return self._client
            self._client = None

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self.cfg.host,
                username=self.cfg.user,
                key_filename=str(self.cfg.key_path),
                port=self.cfg.port,
                timeout=15,
                banner_timeout=15,
                auth_timeout=15,
            )
        except paramiko.AuthenticationException as e:
            raise ConnectionFailed(
                f"SSH auth failed for {self.cfg.user}@{self.cfg.host}. "
                f"Check that key {self.cfg.key} is in authorized_keys on the server. ({e})"
            ) from e
        except (paramiko.SSHException, OSError) as e:
            raise ConnectionFailed(f"Could not reach {self.cfg.host}:{self.cfg.port}. {e}") from e

        self._client = client
        return client

    def exec_php_stdin(self, php_code: str, timeout: int = 60) -> str:
        client = self._client_()
        stdin, stdout, _stderr = client.exec_command("php", timeout=timeout)
        stdin.write(php_code.encode("utf-8"))
        stdin.channel.shutdown_write()
        return stdout.read().decode("utf-8", errors="replace")

    def exec_command(self, command: str, timeout: int = 30) -> tuple[str, str]:
        client = self._client_()
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        return (
            stdout.read().decode("utf-8", errors="replace"),
            stderr.read().decode("utf-8", errors="replace"),
        )

    def read_file(self, remote_path: str, max_bytes: int = 1_000_000) -> str:
        sftp = self._client_().open_sftp()
        try:
            with sftp.file(remote_path, "r") as f:
                data = f.read(max_bytes)
            return data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
        finally:
            sftp.close()

    def write_file(self, remote_path: str, content: str) -> None:
        sftp = self._client_().open_sftp()
        try:
            with sftp.file(remote_path, "w") as f:
                f.write(content)
        finally:
            sftp.close()

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None


# ---------- DDEV ----------


class DDEVConnection(Connection):
    """`ddev exec` subprocess connection. No SFTP — file writes use base64 + PHP."""

    def __init__(self, cfg: DDEVConfig):
        self.cfg = cfg
        if not shutil.which("ddev"):
            raise ConnectionFailed(
                "ddev not found on PATH. Install DDEV (https://ddev.com) or use a different connection type."
            )
        if not self.cfg.project_dir.exists():
            raise ConnectionFailed(f"DDEV project path does not exist: {self.cfg.project_dir}")

    def _run(self, args: list[str], stdin: str | None = None, timeout: int = 60) -> tuple[str, str]:
        result = subprocess.run(
            args,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(self.cfg.project_dir),
            check=False,
        )
        return result.stdout, result.stderr

    def exec_php_stdin(self, php_code: str, timeout: int = 60) -> str:
        out, _err = self._run(["ddev", "exec", "php"], stdin=php_code, timeout=timeout)
        return out

    def exec_command(self, command: str, timeout: int = 30) -> tuple[str, str]:
        return self._run(["ddev", "exec", "bash", "-c", command], timeout=timeout)

    def read_file(self, remote_path: str, max_bytes: int = 1_000_000) -> str:
        # Read via `ddev exec cat` — simplest cross-DDEV way.
        out, err = self._run(
            ["ddev", "exec", "head", "-c", str(max_bytes), remote_path], timeout=30
        )
        if err.strip() and not out:
            raise ConnectionFailed(f"DDEV read_file failed: {err.strip()[:200]}")
        return out

    def write_file(self, remote_path: str, content: str) -> None:
        # SFTP isn't available in DDEV; round-trip via base64 + file_put_contents.
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        php = (
            f"<?php $bytes = file_put_contents('{remote_path}', base64_decode('{encoded}'));"
            f"echo $bytes === false ? 'ERR' : 'OK ' . $bytes;"
        )
        out = self.exec_php_stdin(php)
        if not out.startswith("OK"):
            raise ConnectionFailed(f"DDEV write_file to {remote_path} failed: {out[:200]}")


# ---------- Local subprocess ----------


class LocalConnection(Connection):
    """Direct subprocess against a local PHP install / docker exec / MAMP."""

    def __init__(self, cfg: LocalConfig):
        self.cfg = cfg
        self._php_args = cfg.php_bin.split()
        if not shutil.which(self._php_args[0]) and not self._php_args[0].startswith("/"):
            raise ConnectionFailed(
                f"PHP binary '{self._php_args[0]}' not found on PATH. "
                f"Set php_bin in your profile (e.g. 'docker compose exec web php')."
            )

    @property
    def _cwd(self) -> str | None:
        return str(Path(self.cfg.cwd).expanduser()) if self.cfg.cwd else None

    def exec_php_stdin(self, php_code: str, timeout: int = 60) -> str:
        result = subprocess.run(
            self._php_args,
            input=php_code,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=self._cwd,
            check=False,
        )
        return result.stdout

    def exec_command(self, command: str, timeout: int = 30) -> tuple[str, str]:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=self._cwd,
            check=False,
        )
        return result.stdout, result.stderr

    def read_file(self, remote_path: str, max_bytes: int = 1_000_000) -> str:
        path = Path(remote_path).expanduser()
        with path.open("rb") as f:
            data = f.read(max_bytes)
        return data.decode("utf-8", errors="replace")

    def write_file(self, remote_path: str, content: str) -> None:
        path = Path(remote_path).expanduser()
        path.write_text(content, encoding="utf-8")


# ---------- Factory ----------


class ConnectionFailed(RuntimeError):
    """Connection couldn't be established or a primitive failed."""


def make_connection(spec: dict[str, Any]) -> Connection:
    """Build a Connection from a config dict.

    Expected shape:
        {"type": "ssh", "host": "...", "user": "...", "key": "...", "port": 22}
        {"type": "ddev", "project_path": "~/Sites/foo"}
        {"type": "local", "php_bin": "php", "cwd": "~/Sites/foo"}
    """
    kind = spec.get("type", "ssh").lower()

    if kind == "ssh":
        return SSHConnection(
            SSHConfig(
                host=spec["host"],
                user=spec["user"],
                key=spec.get("key", "~/.ssh/id_ed25519"),
                port=int(spec.get("port", 22)),
            )
        )

    if kind == "ddev":
        return DDEVConnection(
            DDEVConfig(
                project_path=spec["project_path"],
                php_bin=spec.get("php_bin", "ddev exec php"),
            )
        )

    if kind == "local":
        return LocalConnection(
            LocalConfig(
                php_bin=spec.get("php_bin", "php"),
                cwd=spec.get("cwd", ""),
            )
        )

    raise ConnectionFailed(f"Unknown connection type: {kind!r}. Must be one of: ssh, ddev, local.")
