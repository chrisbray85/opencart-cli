"""OpenCart database executor — delegates to a Connection backend.

Three things make this safer than naive SQL string assembly:

  1. Parameterised SQL via mysqli_prepare. Question-mark placeholders only.
     User-supplied values never get concatenated into SQL.

  2. DB credentials and the SQL string are passed to PHP via base64-encoded
     JSON on stdin. Nothing user-controlled lands in the PHP source itself.

  3. Read-only profiles refuse `execute()` and `write_file()` outright,
     before the call even leaves the CLI.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from .config import Profile
from .connection import Connection, ConnectionFailed, make_connection

_NOISE_PATTERNS = ("tput:", "WARNING:", "post-quantum", "upgraded", "Unsuccessful stat")


class DBError(RuntimeError):
    """SQL execution or PHP-side failures."""


class ReadOnlyError(DBError):
    """Profile is in read-only mode and refused a mutation."""


class OpenCartDB:
    """High-level interface for OpenCart's MySQL DB over any Connection backend."""

    def __init__(self, profile: Profile, connection: Connection | None = None):
        self.profile = profile
        self._conn = connection  # injected for testing; else built lazily

    # ---------- Connection management ----------

    @property
    def conn(self) -> Connection:
        if self._conn is None:
            self._conn = make_connection(self.profile.connection)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> OpenCartDB:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ---------- Public API ----------

    def query(
        self,
        sql: str,
        params: list[Any] | None = None,
        timeout: int = 60,
    ) -> list[dict[str, Any]]:
        """Execute a parameterised SQL query. Returns rows as list of dicts.

        Use ? placeholders. Example:
            db.query("SELECT * FROM oc_product WHERE product_id = ?", [123])
        """
        result = self._run_php_query(sql, params or [], execute=False, timeout=timeout)
        if isinstance(result, list):
            return result
        # PHP only returns affected_rows/insert_id dict for queries with no result set
        return []

    def execute(
        self,
        sql: str,
        params: list[Any] | None = None,
        timeout: int = 60,
    ) -> dict[str, int]:
        """Execute INSERT/UPDATE/DELETE/DDL. Returns {affected_rows, insert_id}."""
        if self.profile.is_read_only:
            raise ReadOnlyError(
                f"Profile '{self.profile.name}' is read-only — refusing to execute mutation. "
                f"Remove `read_only: true` from config or use a different profile."
            )
        result = self._run_php_query(sql, params or [], execute=True, timeout=timeout)
        if isinstance(result, dict):
            return {
                "affected_rows": int(result.get("affected_rows", 0)),
                "insert_id": int(result.get("insert_id", 0)),
            }
        # Some statements return a result set even on execute — treat as 0/0
        return {"affected_rows": 0, "insert_id": 0}

    def run_command(self, command: str, timeout: int = 30) -> str:
        """Run a shell command on the target, filtering known shell-init noise."""
        out, err = self.conn.exec_command(command, timeout=timeout)
        if err.strip():
            err_lines = [
                line for line in err.splitlines() if not any(n in line for n in _NOISE_PATTERNS)
            ]
            if err_lines:
                return f"{out}\nSTDERR: {chr(10).join(err_lines)}"
        return out

    def read_file(self, remote_path: str, max_bytes: int = 1_000_000) -> str:
        """Read a file from the target."""
        return self.conn.read_file(remote_path, max_bytes=max_bytes)

    def write_file(self, remote_path: str, content: str) -> None:
        """Write a file to the target. Blocked on read-only profiles."""
        if self.profile.is_read_only:
            raise ReadOnlyError(
                f"Profile '{self.profile.name}' is read-only — refusing file write."
            )
        self.conn.write_file(remote_path, content)

    # ---------- Internal ----------

    def _run_php_query(
        self,
        sql: str,
        params: list[Any],
        execute: bool,
        timeout: int,
    ) -> list[dict[str, Any]] | dict[str, int]:
        """Encode credentials + SQL + params and run the PHP query template."""
        password = self.profile.db_password() or ""
        payload = {
            "sql": sql,
            "params": params,
            "execute": execute,
            "db_user": self.profile.db.user,
            "db_pass": password,
            "db_name": self.profile.db.name,
            "db_host": self.profile.db.host,
            "db_port": self.profile.db.port,
        }
        encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
        php = _PHP_QUERY_TEMPLATE.format(encoded=encoded)

        try:
            out = self.conn.exec_php_stdin(php, timeout=timeout).strip()
        except ConnectionFailed:
            raise
        except Exception as e:
            raise DBError(f"Connection error while running query: {e}") from e

        if not out:
            raise DBError(
                "Empty response from PHP — connection or auth may have failed. "
                "Try `opencart doctor` to diagnose."
            )

        try:
            result = json.loads(out)
        except json.JSONDecodeError as e:
            raise DBError(f"Invalid JSON from PHP: {out[:300]}") from e

        if isinstance(result, dict) and "error" in result:
            raise DBError(result["error"])

        return result


# ---------- Connection pool ----------

_POOL: dict[str, OpenCartDB] = {}


def get_db(profile: Profile) -> OpenCartDB:
    """Process-wide pooled DB connection keyed by profile name + connection spec.

    Subsequent calls within the same process reuse the same SSH/DDEV/local
    connection, dramatically reducing latency for shell/REPL/watch commands.
    """
    key = f"{profile.name}::{profile.connection_type}"
    db = _POOL.get(key)
    if db is None:
        db = OpenCartDB(profile)
        _POOL[key] = db
    return db


def close_all() -> None:
    """Tear down every pooled connection (call on shutdown)."""
    for db in list(_POOL.values()):
        try:
            db.close()
        except Exception:
            pass
    _POOL.clear()


# ---------- PHP template ----------
# Receives ALL inputs via base64-encoded JSON on stdin → decoded once →
# uses mysqli_prepare for parameter binding. No user-supplied string is
# ever concatenated into SQL or shell.

_PHP_QUERY_TEMPLATE = r"""<?php
error_reporting(0);
$payload = json_decode(base64_decode('{encoded}'), true);
if (!$payload) {{
    echo json_encode(["error" => "PHP could not decode payload"]);
    exit;
}}

$mysqli = new mysqli(
    $payload['db_host'] ?? 'localhost',
    $payload['db_user'],
    $payload['db_pass'],
    $payload['db_name'],
    (int)($payload['db_port'] ?? 3306)
);
if ($mysqli->connect_error) {{
    echo json_encode(["error" => "DB connect failed: " . $mysqli->connect_error]);
    exit;
}}
$mysqli->set_charset('utf8mb4');

$sql = $payload['sql'];
$params = $payload['params'] ?? [];
$execute = !empty($payload['execute']);

if (count($params) === 0) {{
    $result = $mysqli->query($sql);
    if ($result === false) {{
        echo json_encode(["error" => "Query failed: " . $mysqli->error]);
        exit;
    }}
    if ($result === true) {{
        echo json_encode([
            "affected_rows" => $mysqli->affected_rows,
            "insert_id" => $mysqli->insert_id,
        ]);
        exit;
    }}
    $rows = [];
    while ($row = $result->fetch_assoc()) {{ $rows[] = $row; }}
    echo json_encode($rows);
    $mysqli->close();
    exit;
}}

$stmt = $mysqli->prepare($sql);
if ($stmt === false) {{
    echo json_encode(["error" => "Prepare failed: " . $mysqli->error]);
    exit;
}}

$types = '';
$bind_values = [];
foreach ($params as $p) {{
    if (is_int($p)) {{ $types .= 'i'; }}
    elseif (is_float($p)) {{ $types .= 'd'; }}
    else {{ $types .= 's'; }}
    $bind_values[] = $p;
}}
if (!empty($bind_values)) {{
    $refs = [];
    foreach ($bind_values as $k => $v) {{ $refs[$k] = &$bind_values[$k]; }}
    array_unshift($refs, $types);
    call_user_func_array([$stmt, 'bind_param'], $refs);
}}

if (!$stmt->execute()) {{
    echo json_encode(["error" => "Execute failed: " . $stmt->error]);
    exit;
}}

if ($execute) {{
    echo json_encode([
        "affected_rows" => $stmt->affected_rows,
        "insert_id" => $stmt->insert_id,
    ]);
}} else {{
    $result = $stmt->get_result();
    if ($result === false) {{
        echo json_encode([
            "affected_rows" => $stmt->affected_rows,
            "insert_id" => $stmt->insert_id,
        ]);
    }} else {{
        $rows = [];
        while ($row = $result->fetch_assoc()) {{ $rows[] = $row; }}
        echo json_encode($rows);
    }}
}}
$stmt->close();
$mysqli->close();
"""
