"""`opencart profile ...` — profile management."""

from __future__ import annotations

import typer

from opencart_cli.context import CLIContext
from opencart_cli.core.config import save_config
from opencart_cli.core.secrets import delete_secret
from opencart_cli.formatters import info, render, success, warn

app = typer.Typer(no_args_is_help=True, help="Manage store profiles.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List configured profiles."""
    cli: CLIContext = ctx.obj
    rows = []
    for name, p in cli.config.profiles.items():
        rows.append(
            {
                "name": name,
                "default": "*" if name == cli.config.default_profile else "",
                "type": p.connection_type,
                "host_or_path": p.connection.get("host") or p.connection.get("project_path", ""),
                "db": f"{p.db.user}@{p.db.host}/{p.db.name}",
                "read_only": p.is_read_only,
                "description": p.description,
            }
        )
    if not rows:
        info("No profiles yet. Run `opencart init` to create one.")
        return
    render(rows, fmt=cli.format, title="Profiles")


@app.command("use")
def use(ctx: typer.Context, name: str) -> None:
    """Set the default profile."""
    cli: CLIContext = ctx.obj
    if name not in cli.config.profiles:
        warn(f"Profile '{name}' does not exist.")
        raise typer.Exit(1)
    cli.config.default_profile = name
    save_config(cli.config)
    success(f"Default profile is now '{name}'.")


@app.command("remove")
def remove(
    ctx: typer.Context,
    name: str,
    keep_secret: bool = typer.Option(
        False, "--keep-secret", help="Don't delete the stored DB password from the keychain."
    ),
) -> None:
    """Remove a profile from the config."""
    cli: CLIContext = ctx.obj
    if name not in cli.config.profiles:
        warn(f"Profile '{name}' does not exist.")
        raise typer.Exit(1)
    del cli.config.profiles[name]
    if cli.config.default_profile == name:
        cli.config.default_profile = next(iter(cli.config.profiles), "")
    save_config(cli.config)
    if not keep_secret:
        delete_secret(name, "db_password")
    success(f"Removed profile '{name}'.")


@app.command("show")
def show(ctx: typer.Context, name: str | None = typer.Argument(None)) -> None:
    """Show the active or named profile in full."""
    cli: CLIContext = ctx.obj
    profile = cli.config.get_profile(name)
    data = {
        "name": profile.name,
        "description": profile.description,
        "connection": profile.connection,
        "db": {
            "user": profile.db.user,
            "name": profile.db.name,
            "host": profile.db.host,
            "port": profile.db.port,
            "password": "(in keychain)" if profile.db_password() else "(not set)",
        },
        "opencart": {
            "root": profile.opencart.root,
            "storage": profile.opencart.effective_storage,
            "version": profile.opencart.version,
            "table_prefix": profile.opencart.table_prefix,
        },
        "read_only": profile.is_read_only,
    }
    render(data, fmt=cli.format, title=f"Profile: {profile.name}")
