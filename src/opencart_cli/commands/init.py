"""`opencart init` — interactive setup wizard for a new profile.

Branches by connection type:
  - ssh:   host, user, key path
  - ddev:  local project path
  - local: php_bin command, working directory

Stores config at ~/.config/opencart-cli/config.yaml (XDG dir).
Stores DB password in OS keychain (with env-var fallback for CI).
"""

from __future__ import annotations

from typing import Any

import typer
from rich.prompt import Confirm, Prompt

from opencart_cli.context import CLIContext
from opencart_cli.core.config import (
    DBConnection,
    OpenCartInstall,
    Profile,
    save_config,
)
from opencart_cli.core.connection import (
    ConnectionFailed,
    make_connection,
)
from opencart_cli.core.db import DBError, OpenCartDB
from opencart_cli.core.secrets import keyring_available, set_secret
from opencart_cli.formatters import _console_err, error, success, warn


def run(
    ctx: typer.Context,
    name: str = typer.Option(None, "--name", help="Profile name (will prompt if omitted)."),
    test: bool = typer.Option(
        True, "--test/--no-test", help="Test the connection after configuring."
    ),
) -> None:
    """Walk through creating a new store profile."""
    cli: CLIContext = ctx.obj

    _console_err.print("\n[bold cyan]Welcome to opencart-cli![/bold cyan]")
    _console_err.print(
        "This wizard will create a [bold]new store profile[/bold]. "
        "Press Ctrl+C at any time to abort.\n"
    )

    # 1. Profile name
    if not name:
        existing = ", ".join(cli.config.profiles) or "(none yet)"
        _console_err.print(f"[dim]Existing profiles:[/dim] {existing}")
        name = Prompt.ask(
            "Profile name (e.g. 'rewnd-prod', 'staging', 'localdev')",
            default="default",
        ).strip()
    if name in cli.config.profiles:
        if not Confirm.ask(f"Profile '{name}' already exists. Overwrite?", default=False):
            error("Aborted.")
            raise typer.Exit(1)

    # 2. Connection type
    _console_err.print("\n[bold]Connection type:[/bold]")
    _console_err.print(
        "  [cyan]ssh[/cyan]   — remote VPS or shared hosting (default)\n"
        "  [cyan]ddev[/cyan]  — local DDEV development environment\n"
        "  [cyan]local[/cyan] — local PHP install, Docker Compose, or MAMP"
    )
    conn_type = Prompt.ask(
        "Choose connection type",
        choices=["ssh", "ddev", "local"],
        default="ssh",
    )

    connection: dict[str, Any] = {"type": conn_type}
    if conn_type == "ssh":
        connection["host"] = Prompt.ask("SSH host (IP or hostname)")
        connection["user"] = Prompt.ask("SSH user")
        connection["key"] = Prompt.ask("SSH private key path", default="~/.ssh/id_ed25519")
        port = Prompt.ask("SSH port", default="22")
        if port != "22":
            connection["port"] = int(port)
    elif conn_type == "ddev":
        connection["project_path"] = Prompt.ask(
            "Local DDEV project path (the directory you run `ddev` from)"
        )
    else:  # local
        connection["php_bin"] = Prompt.ask(
            "PHP command",
            default="php",
        )
        cwd = Prompt.ask("Working directory (leave blank for current)", default="")
        if cwd:
            connection["cwd"] = cwd

    # 3. Database
    _console_err.print("\n[bold]MySQL database:[/bold]")
    db_user = Prompt.ask("DB user", default="db" if conn_type == "ddev" else None)
    db_name = Prompt.ask("DB name", default="db" if conn_type == "ddev" else None)
    db_pass = Prompt.ask("DB password (will be stored securely)", password=True)
    default_host = {"ssh": "localhost", "ddev": "db", "local": "127.0.0.1"}[conn_type]
    db_host = Prompt.ask("DB host", default=default_host)
    db_port = Prompt.ask("DB port", default="3306")

    # 4. OpenCart install
    _console_err.print("\n[bold]OpenCart install:[/bold]")
    default_root = "/var/www/html" if conn_type == "ddev" else ""
    oc_root = Prompt.ask("OpenCart root directory", default=default_root or None)
    oc_version = Prompt.ask(
        "OpenCart version", choices=["auto", "2.x", "3.x", "4.x"], default="auto"
    )
    table_prefix = Prompt.ask("Table prefix", default="oc_")

    # 5. Safety
    _console_err.print("\n[bold]Safety:[/bold]")
    read_only_default = name.lower().startswith("prod")
    read_only = Confirm.ask(
        "Mark this profile as read-only? (mutations will be refused)",
        default=read_only_default,
    )
    description = Prompt.ask("Optional description", default="")

    # 6. Build + save profile
    profile = Profile(
        name=name,
        description=description,
        read_only=read_only,
        connection=connection,
        db=DBConnection(user=db_user, name=db_name, host=db_host, port=int(db_port)),
        opencart=OpenCartInstall(
            root=oc_root,
            version=oc_version,
            table_prefix=table_prefix,
        ),
    )
    cli.config.profiles[name] = profile
    if not cli.config.default_profile or Confirm.ask(
        f"Make '{name}' the default profile?",
        default=(len(cli.config.profiles) == 1),
    ):
        cli.config.default_profile = name

    # Save config
    cfg_path = save_config(cli.config)
    success(f"Config saved to {cfg_path}")

    # Save secret
    if keyring_available():
        if set_secret(name, "db_password", db_pass):
            success("DB password saved to OS keychain.")
        else:
            warn(
                "Couldn't save to keychain. Set the env var "
                f"OPENCART_{name.upper().replace('-', '_')}_DB_PASS=... before running commands."
            )
    else:
        env_var = f"OPENCART_{name.upper().replace('-', '_')}_DB_PASS"
        warn(
            f"OS keychain not available. Export {env_var}=... in your shell "
            f"or pass it inline before each command."
        )

    # 7. Test connection
    if test:
        _console_err.print("\n[bold]Testing connection...[/bold]")
        try:
            conn = make_connection(connection)
            db = OpenCartDB(profile, connection=conn)
            rows = db.query("SELECT 1 AS ping")
            if rows and rows[0].get("ping") == 1:
                success("Connection works! 🎉")
            else:
                warn(f"Connection returned unexpected: {rows}")
            db.close()
        except (ConnectionFailed, DBError) as e:
            error(f"Connection failed: {e}")
            _console_err.print(
                f"\nRun [cyan]opencart doctor --profile {name}[/cyan] for detailed diagnostics."
            )
            raise typer.Exit(1) from e

    # 8. Next steps
    _console_err.print(
        "\n[bold green]Done![/bold green] Try:\n"
        "  [cyan]opencart products list[/cyan]\n"
        "  [cyan]opencart sales summary[/cyan]\n"
        '  [cyan]opencart ask "how many products do I have?"[/cyan]\n'
    )
