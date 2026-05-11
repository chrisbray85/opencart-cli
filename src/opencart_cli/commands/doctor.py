"""`opencart doctor` — diagnose SSH/DDEV/local connection, MySQL, OpenCart install."""

from __future__ import annotations

import typer

from opencart_cli.context import CLIContext
from opencart_cli.core import operations
from opencart_cli.core.connection import ConnectionFailed, make_connection
from opencart_cli.core.db import DBError, OpenCartDB
from opencart_cli.core.version import effective_version
from opencart_cli.formatters import _console_err, error, success, warn


def run(ctx: typer.Context) -> None:
    """Run a series of health checks against the active profile."""
    cli: CLIContext = ctx.obj
    profile = cli.profile()
    _console_err.print(f"\n[bold]Diagnosing profile:[/bold] [cyan]{profile.name}[/cyan]")
    _console_err.print(f"  Connection: [cyan]{profile.connection_type}[/cyan]")
    _console_err.print()

    overall_ok = True

    # 1. Connection
    try:
        conn = make_connection(profile.connection)
        success(f"Connection: built {type(conn).__name__}")
    except ConnectionFailed as e:
        error(f"Connection: {e}")
        raise typer.Exit(1) from e

    # 2. Shell exec
    try:
        out, _err = conn.exec_command("echo OPENCART_CLI_DOCTOR_PING", timeout=10)
        if "OPENCART_CLI_DOCTOR_PING" in out:
            success("Shell exec: responsive")
        else:
            warn(f"Shell exec: returned unexpected output: {out[:80]!r}")
            overall_ok = False
    except Exception as e:
        error(f"Shell exec: {e}")
        overall_ok = False

    # 3. PHP available
    try:
        php_out = conn.exec_php_stdin("<?php echo PHP_VERSION;", timeout=10).strip()
        if php_out and php_out[0].isdigit():
            success(f"PHP: {php_out}")
        else:
            error(f"PHP: unexpected output: {php_out[:80]!r}")
            overall_ok = False
    except Exception as e:
        error(f"PHP: {e}")
        overall_ok = False

    # 4. MySQL via PHP
    db = OpenCartDB(profile, connection=conn)
    try:
        version_rows = db.query("SELECT VERSION() AS v")
        success(f"MySQL: {version_rows[0]['v']}")
    except DBError as e:
        error(f"MySQL: {e}")
        if "password" in str(e).lower() or "access denied" in str(e).lower():
            warn(
                "Hint: DB password may be missing from the keychain. "
                f"Set with: opencart-cli will prompt during `opencart init --reconfigure {profile.name}`"
            )
        overall_ok = False
        conn.close()
        raise typer.Exit(1 if not overall_ok else 0) from e

    # 5. OpenCart tables present
    try:
        tables = operations.list_tables(db, pattern=f"{profile.opencart.table_prefix}product")
        if tables:
            success(f"OpenCart tables: found ({profile.opencart.table_prefix}product exists)")
        else:
            warn(
                f"OpenCart tables: '{profile.opencart.table_prefix}product' not found. "
                f"Check table_prefix in profile."
            )
            overall_ok = False
    except DBError as e:
        error(f"OpenCart tables: {e}")
        overall_ok = False

    # 6. Version detection
    try:
        version = effective_version(db)
        success(f"OpenCart version: {version}")
    except Exception as e:
        warn(f"OpenCart version: could not detect ({e})")

    # 7. Read-only mode
    if profile.is_read_only:
        _console_err.print(
            f"\n[yellow]ℹ[/yellow] Profile is in [bold yellow]read-only[/bold yellow] mode "
            f"(reason: {'name starts with prod*' if profile.name.lower().startswith('prod') else 'config flag'})"
        )

    conn.close()
    _console_err.print()
    if overall_ok:
        success("All checks passed.")
    else:
        error("Some checks failed — see above.")
        raise typer.Exit(1)
