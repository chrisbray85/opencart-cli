"""`opencart stock ...` — stock reports."""

from __future__ import annotations

import typer

from opencart_cli.context import CLIContext
from opencart_cli.core import operations
from opencart_cli.formatters import render

app = typer.Typer(no_args_is_help=True, help="Stock reports.")


@app.command("low")
def low(
    ctx: typer.Context,
    threshold: int = typer.Option(
        15, "--threshold", "-t", help="Stock level at or below which to report."
    ),
) -> None:
    """Products with stock at or below threshold, lowest first."""
    cli: CLIContext = ctx.obj
    rows = operations.low_stock_report(cli.db(), threshold=threshold)
    render(
        rows,
        fmt=cli.format,
        title=f"Low stock (≤ {threshold})",
        columns=["product_id", "model", "sku", "name", "quantity", "price"],
        numeric=["product_id", "quantity"],
        money=["price"],
    )
