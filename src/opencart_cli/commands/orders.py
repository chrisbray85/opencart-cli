"""`opencart orders ...` — list and inspect orders."""

from __future__ import annotations

import typer

from opencart_cli.context import CLIContext
from opencart_cli.core import operations
from opencart_cli.formatters import error, render

app = typer.Typer(no_args_is_help=True, help="Orders.")


@app.command("list")
def list_(
    ctx: typer.Context,
    days: int = typer.Option(7, "--days", "-d", help="Look back N days."),
    status: int | None = typer.Option(None, "--status", help="Filter by order_status_id."),
    min_total: float | None = typer.Option(None, "--min-total", help="Filter by minimum total."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max rows to return."),
) -> None:
    """Recent orders, newest first."""
    cli: CLIContext = ctx.obj
    rows = operations.list_orders(
        cli.db(), days=days, status=status, min_total=min_total, limit=limit
    )
    render(
        rows,
        fmt=cli.format,
        title=f"Orders ({len(rows)}, last {days}d)",
        columns=[
            "order_id",
            "date_added",
            "firstname",
            "lastname",
            "email",
            "total",
            "status",
            "payment_method",
        ],
        numeric=["order_id"],
        money=["total"],
    )


@app.command("get")
def get(ctx: typer.Context, order_id: int) -> None:
    """Full detail: header, line items, status history."""
    cli: CLIContext = ctx.obj
    data = operations.get_order(cli.db(), order_id)
    if not data:
        error(f"Order {order_id} not found.")
        raise typer.Exit(1)
    if cli.format != "auto" and cli.format != "table":
        render(data, fmt=cli.format)
        return
    render(data["order"], fmt="table", title=f"Order {order_id}")
    if data["products"]:
        render(data["products"], fmt="table", title="Line items", money=["price", "total"])
    if data["history"]:
        render(data["history"], fmt="table", title="Status history")
