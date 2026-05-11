"""`opencart settings ...` — read/write OpenCart settings."""

from __future__ import annotations

import typer

from opencart_cli.confirm import confirm_mutation
from opencart_cli.context import CLIContext
from opencart_cli.core import operations
from opencart_cli.formatters import error, render, success

app = typer.Typer(no_args_is_help=True, help="OpenCart settings.")


@app.command("list")
def list_(
    ctx: typer.Context,
    group: str | None = typer.Option(None, "--group", "-g", help="Filter by setting group/code."),
    key: str | None = typer.Option(None, "--key", "-k", help="Filter by exact key."),
) -> None:
    """List OpenCart settings."""
    cli: CLIContext = ctx.obj
    rows = operations.get_settings(cli.db(), group=group, key=key)
    render(
        rows,
        fmt=cli.format,
        title=f"Settings ({len(rows)})",
        columns=["code", "key", "value", "store_id"],
    )


@app.command("set")
def set_cmd(
    ctx: typer.Context,
    group: str = typer.Argument(..., help="Group/code, e.g. 'config'."),
    key: str = typer.Argument(..., help="Key, e.g. 'config_email'."),
    value: str = typer.Argument(..., help="New value."),
) -> None:
    """Update a single setting."""
    cli: CLIContext = ctx.obj
    current = operations.get_settings(cli.db(), group=group, key=key)
    if not current:
        error(f"Setting {group}.{key} not found.")
        raise typer.Exit(1)
    if not confirm_mutation(
        title=f"Set {group}.{key}",
        plan={"old": current[0]["value"], "new": value},
        yes=cli.yes,
        dry_run=cli.dry_run,
    ):
        error("Aborted.")
        raise typer.Exit(1)
    operations.set_setting(cli.db(), group, key, value)
    success(f"Updated {group}.{key}.")
