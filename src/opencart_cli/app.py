"""Main typer application — global flags, command registration.

Run via `opencart` (or `oc`) after `pip install opencart-cli`.
"""

from __future__ import annotations

import sys

import typer
from rich.traceback import install as install_rich_traceback

from . import __version__
from .commands import (
    ask,
    customers,
    demo,
    doctor,
    init,
    orders,
    products,
    profile,
    sales,
    settings,
    shell,
    sql,
    stock,
    watch,
)
from .context import CLIContext
from .core.config import ConfigError, load_config
from .core.db import close_all
from .formatters import Format, error

install_rich_traceback(show_locals=False)

app = typer.Typer(
    name="opencart",
    help=(
        "The OpenCart CLI you wish came in the box.\n\n"
        "Query, edit, and operate your OpenCart store from the terminal. "
        "AI-powered queries, interactive shell, live order watching."
    ),
    add_completion=True,
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"opencart-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    profile: str | None = typer.Option(
        None, "--profile", "-p", help="Profile name (overrides default and OPENCART_PROFILE)."
    ),
    format: Format = typer.Option(
        "auto", "--format", "-f", help="Output format: auto, table, json, yaml, csv."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would change without applying it."
    ),
    read_only: bool = typer.Option(
        False, "--read-only", help="Force read-only mode for this invocation."
    ),
    version: bool = typer.Option(
        False, "--version", "-V", callback=version_callback, is_eager=True, help="Show version."
    ),
) -> None:
    """Global flags. See `opencart <subcommand> --help` for details."""
    try:
        config = load_config()
    except ConfigError as e:
        error(str(e))
        raise typer.Exit(1) from e

    ctx.obj = CLIContext(
        config=config,
        profile_override=profile,
        format=format,
        yes=yes,
        dry_run=dry_run,
        force_read_only=read_only,
    )


# ---------- Register subcommands ----------

app.add_typer(profile.app, name="profile", help="Manage store profiles.")
app.add_typer(demo.app, name="demo", help="Try the CLI with canned data — no profile needed.")
app.add_typer(products.app, name="products", help="List, inspect, and update products.")
app.add_typer(orders.app, name="orders", help="List and inspect orders.")
app.add_typer(customers.app, name="customers", help="List and search customers.")
app.add_typer(settings.app, name="settings", help="Read and write OpenCart settings.")
app.add_typer(stock.app, name="stock", help="Stock reporting and low-stock alerts.")
app.add_typer(sales.app, name="sales", help="Sales reporting with sparklines.")

# Top-level commands
app.command("init", help="Interactive setup wizard for a new store profile.")(init.run)
app.command("doctor", help="Diagnose SSH, MySQL, and OpenCart configuration.")(doctor.run)
app.command("ask", help="Ask a question in natural language — generates SQL and runs it.")(ask.run)
app.command("shell", help="Interactive REPL with persistent connection.")(shell.run)
app.command("watch", help="Watch for new orders in real time.")(watch.run)
app.command("sql", help="Run a raw SELECT/SHOW/DESCRIBE query (safety-checked).")(sql.run)


@app.command("version", help="Print version and exit.")
def version_cmd() -> None:
    typer.echo(f"opencart-cli {__version__}")


def _shutdown() -> None:
    close_all()


# Ensure pooled connections close on normal exit
import atexit  # noqa: E402

atexit.register(_shutdown)


if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)
