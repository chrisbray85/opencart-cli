"""`opencart customers ...` — list and search customers."""

from __future__ import annotations

import typer

from opencart_cli.context import CLIContext
from opencart_cli.core import operations
from opencart_cli.formatters import render

app = typer.Typer(no_args_is_help=True, help="Customers.")


@app.command("list")
def list_(
    ctx: typer.Context,
    search: str | None = typer.Option(
        None, "--search", "-s", help="Email / name / phone substring."
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Max rows to return."),
) -> None:
    """List or search customers."""
    cli: CLIContext = ctx.obj
    rows = operations.list_customers(cli.db(), search=search, limit=limit)
    render(
        rows,
        fmt=cli.format,
        title=f"Customers ({len(rows)})",
        columns=[
            "customer_id",
            "firstname",
            "lastname",
            "email",
            "telephone",
            "status",
            "date_added",
        ],
        numeric=["customer_id", "status"],
    )
