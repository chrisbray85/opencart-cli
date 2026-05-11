"""Audit log — JSONL record of every mutation the CLI performs.

One line per change, stored at <config_dir>/audit.jsonl. Lets users see
what's been changed (and who/when/from where), and underpins future
rollback/snapshot tooling.
"""

from __future__ import annotations

import getpass
import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import config_dir


def audit_log_path() -> Path:
    return config_dir() / "audit.jsonl"


def log_mutation(
    profile: str,
    action: str,
    target: str,
    before: Any | None = None,
    after: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append a single mutation record. Best-effort — never raises."""
    try:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "profile": profile,
            "action": action,
            "target": target,
            "before": before,
            "after": after,
            "user": getpass.getuser(),
            "host": socket.gethostname(),
            "metadata": metadata or {},
        }
        path = audit_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass  # audit must never break the actual operation


def read_recent(limit: int = 50) -> list[dict[str, Any]]:
    """Read the most recent N audit entries."""
    path = audit_log_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in reversed(lines[-limit:]):
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
