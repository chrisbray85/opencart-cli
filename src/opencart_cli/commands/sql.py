"""`opencart sql ...` — raw SELECT/SHOW/DESCRIBE escape hatch (safety-checked)."""

from __future__ import annotations

import sys

import typer

from opencart_cli.context import CLIContext
from opencart_cli.core import operations
from opencart_cli.formatters import error, render


def run(
    ctx: typer.Context,
    query: str = typer.Argument(
        None,
        help="SQL to run. Use '-' to read from stdin. Only SELECT/SHOW/DESCRIBE/EXPLAIN allowed.",
    ),
) -> None:
    """Run a raw SQL query. INSERT/UPDATE/DELETE/DDL are blocked here — use the dedicated commands instead."""
    cli: CLIContext = ctx.obj
    if query is None or query == "-":
        query = sys.stdin.read()
    if not query.strip():
        error("No SQL provided.")
        raise typer.Exit(1)
    try:
        rows = operations.safe_select(cli.db(), query)
    except ValueError as e:
        error(str(e))
        raise typer.Exit(1) from e
    render(rows, fmt=cli.format, title=f"{len(rows)} rows")
