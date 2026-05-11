"""`opencart products ...` — list, inspect, update products."""

from __future__ import annotations

import typer

from opencart_cli.confirm import confirm_mutation
from opencart_cli.context import CLIContext
from opencart_cli.core import operations
from opencart_cli.formatters import error, render, success

app = typer.Typer(no_args_is_help=True, help="Products.")


@app.command("list")
def list_(
    ctx: typer.Context,
    search: str | None = typer.Option(None, "--search", "-s", help="Name / model / SKU substring."),
    status: int | None = typer.Option(None, "--status", help="1 = enabled, 0 = disabled."),
    low_stock_under: int | None = typer.Option(
        None, "--low-stock-under", help="Only products with stock below this number."
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Max rows to return."),
) -> None:
    """List products with optional filters."""
    cli: CLIContext = ctx.obj
    rows = operations.list_products(
        cli.db(), search=search, status=status, low_stock_under=low_stock_under, limit=limit
    )
    render(
        rows,
        fmt=cli.format,
        title=f"Products ({len(rows)})",
        columns=["product_id", "model", "sku", "name", "price", "quantity", "status"],
        numeric=["product_id", "quantity", "status"],
        money=["price"],
    )


@app.command("get")
def get(ctx: typer.Context, product_id: int) -> None:
    """Full detail for a single product."""
    cli: CLIContext = ctx.obj
    product = operations.get_product(cli.db(), product_id)
    if not product:
        error(f"Product {product_id} not found.")
        raise typer.Exit(1)
    render(product, fmt=cli.format, title=f"Product {product_id}")


@app.command("update")
def update(
    ctx: typer.Context,
    product_id: int,
    price: float | None = typer.Option(None, "--price"),
    quantity: int | None = typer.Option(None, "--quantity", "--stock"),
    status: int | None = typer.Option(None, "--status", help="0 = disabled, 1 = enabled"),
    model: str | None = typer.Option(None, "--model"),
    sku: str | None = typer.Option(None, "--sku"),
) -> None:
    """Update one or more fields on a product (dry-run by default)."""
    cli: CLIContext = ctx.obj
    updates: dict = {
        k: v
        for k, v in {
            "price": price,
            "quantity": quantity,
            "status": status,
            "model": model,
            "sku": sku,
        }.items()
        if v is not None
    }
    if not updates:
        error("Nothing to update. Pass at least one field flag.")
        raise typer.Exit(1)
    before = operations.get_product(cli.db(), product_id)
    if not before:
        error(f"Product {product_id} not found.")
        raise typer.Exit(1)
    plan = {f"{k} ({before.get(k)} → {v})": "" for k, v in updates.items()}
    if not confirm_mutation(
        title=f"Update product {product_id} ({before.get('name')})",
        plan={k.split(" (")[0]: k.split("(", 1)[1].rstrip(")") for k in plan},
        yes=cli.yes,
        dry_run=cli.dry_run,
    ):
        error("Aborted.")
        raise typer.Exit(1)
    for field, value in updates.items():
        operations.update_product_field(cli.db(), product_id, field, value)
    success(f"Updated product {product_id}: {', '.join(updates.keys())}.")
