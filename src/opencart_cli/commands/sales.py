"""`opencart sales ...` — sales reports with sparklines."""

from __future__ import annotations

import typer

from opencart_cli.context import CLIContext
from opencart_cli.core import operations
from opencart_cli.formatters import console, render, sparkline

app = typer.Typer(no_args_is_help=True, help="Sales reports.")


@app.command("summary")
def summary(
    ctx: typer.Context,
    days: int = typer.Option(30, "--days", "-d", help="Look back N days."),
) -> None:
    """Headline figures + daily breakdown sparkline + top sellers."""
    cli: CLIContext = ctx.obj
    data = operations.sales_summary(cli.db(), days=days)

    if cli.format in ("json", "yaml", "csv"):
        render(data, fmt=cli.format)
        return

    # Pretty TTY output
    console.print(f"\n[bold]Sales — last {days} days[/bold]")
    console.print(f"  Revenue: [green]£{data['revenue']:,.2f}[/green]")
    console.print(f"  Orders:  [cyan]{data['orders']:,}[/cyan]")
    console.print(f"  AOV:     [cyan]£{data['aov']:,.2f}[/cyan]")

    daily = data.get("daily", [])
    if daily:
        revenue_series = [float(d["revenue"]) for d in daily]
        order_series = [int(d["orders"]) for d in daily]
        console.print(f"  Daily £: [cyan]{sparkline(revenue_series)}[/cyan]")
        console.print(f"  Daily n: [cyan]{sparkline(order_series)}[/cyan]")

    if data.get("top_products"):
        render(
            data["top_products"],
            fmt="table",
            title="Top sellers",
            columns=["product_id", "name", "qty", "revenue"],
            numeric=["product_id", "qty"],
            money=["revenue"],
        )


@app.command("daily")
def daily(
    ctx: typer.Context,
    days: int = typer.Option(30, "--days", "-d", help="Look back N days."),
) -> None:
    """Daily orders + revenue breakdown."""
    cli: CLIContext = ctx.obj
    data = operations.sales_summary(cli.db(), days=days)
    render(
        data["daily"],
        fmt=cli.format,
        title=f"Daily sales — last {days}d",
        columns=["day", "orders", "revenue"],
        numeric=["orders"],
        money=["revenue"],
        sparkline_col="revenue",
    )
