"""`opencart demo ...` — try the CLI without setting up a profile.

Renders the real formatters against canned data, so new users can see
exactly what they'd get from a real store before configuring anything.
Also drives the README/release GIF.

  opencart demo sales      # the sparkline + top sellers (the money shot)
  opencart demo products   # a low-stock table
  opencart demo orders     # recent orders
  opencart demo doctor     # fake clean health check
  opencart demo all        # walk through all of the above
"""

from __future__ import annotations

import time
from typing import Any

import typer

from opencart_cli.formatters import (
    _console_err,
    console,
    error,
    render,
    sparkline,
    success,
)

app = typer.Typer(no_args_is_help=True, help="Try the CLI with canned data — no profile needed.")


# ---------- Canned fixtures (generic e-commerce store) ----------


_PRODUCTS_LOW_STOCK: list[dict[str, Any]] = [
    {"product_id": 42, "model": "MOUSE-WL-01", "sku": "WLM-001", "name": "Wireless Mouse Pro", "quantity": 3, "price": 29.99, "status": 1},
    {"product_id": 73, "model": "KBD-MECH-BRN", "sku": "MKB-BRN-87", "name": "Mechanical Keyboard - Brown Switches", "quantity": 4, "price": 89.99, "status": 1},
    {"product_id": 18, "model": "HUB-USBC-4P", "sku": "UCH-4PT", "name": "USB-C Hub 4-Port", "quantity": 2, "price": 24.99, "status": 1},
    {"product_id": 91, "model": "CAM-HD-1080", "sku": "WC-1080", "name": "Webcam HD 1080p", "quantity": 1, "price": 49.99, "status": 1},
]

_ORDERS_RECENT: list[dict[str, Any]] = [
    {"order_id": 1042, "date_added": "2026-05-11 11:42:15", "firstname": "Sarah", "lastname": "Chen", "email": "s.chen@example.com", "total": 134.98, "status": "Processing", "payment_method": "Card"},
    {"order_id": 1041, "date_added": "2026-05-11 11:38:02", "firstname": "Marco", "lastname": "Bianchi", "email": "marco@example.com", "total": 89.99, "status": "Complete", "payment_method": "PayPal"},
    {"order_id": 1040, "date_added": "2026-05-11 10:54:31", "firstname": "Aisha", "lastname": "Patel", "email": "aisha.p@example.com", "total": 219.50, "status": "Complete", "payment_method": "Card"},
    {"order_id": 1039, "date_added": "2026-05-11 09:22:18", "firstname": "Ben", "lastname": "Walker", "email": "ben@example.com", "total": 24.99, "status": "Complete", "payment_method": "Apple Pay"},
    {"order_id": 1038, "date_added": "2026-05-10 22:11:47", "firstname": "Yuki", "lastname": "Tanaka", "email": "y.tanaka@example.com", "total": 419.97, "status": "Complete", "payment_method": "Card"},
]

_SALES_SUMMARY: dict[str, Any] = {
    "period_days": 7,
    "revenue": 12847.50,
    "orders": 142,
    "aov": 90.47,
    "daily_revenue": [1620.40, 1820.10, 2105.00, 2480.50, 1990.30, 1390.20, 1441.00],
    "top_products": [
        {"product_id": 18, "name": "Mechanical Keyboard - Brown Switches", "qty": 34, "revenue": 2550.00},
        {"product_id": 42, "name": "Wireless Mouse Pro", "qty": 56, "revenue": 1680.00},
        {"product_id": 73, "name": "USB-C Hub 4-Port", "qty": 38, "revenue": 760.00},
        {"product_id": 91, "name": "Webcam HD 1080p", "qty": 12, "revenue": 599.88},
        {"product_id": 27, "name": "Standing Desk Mat", "qty": 9, "revenue": 359.91},
    ],
}


# ---------- Commands ----------


@app.command("products")
def products() -> None:
    """Sample low-stock report — generic e-commerce products."""
    render(
        _PRODUCTS_LOW_STOCK,
        fmt="table",
        title="Demo: products with stock ≤ 5",
        columns=["product_id", "model", "sku", "name", "quantity", "price"],
        numeric=["product_id", "quantity"],
        money=["price"],
    )
    _console_err.print(
        "\n[dim]This is canned demo data. Run `opencart init` to connect a real store.[/dim]"
    )


@app.command("orders")
def orders() -> None:
    """Sample recent-orders listing."""
    render(
        _ORDERS_RECENT,
        fmt="table",
        title="Demo: recent orders",
        columns=["order_id", "date_added", "firstname", "lastname", "email", "total", "status", "payment_method"],
        numeric=["order_id"],
        money=["total"],
    )
    _console_err.print("\n[dim]This is canned demo data.[/dim]")


@app.command("sales")
def sales() -> None:
    """Sample sales summary — the headline view with sparklines + top sellers."""
    data = _SALES_SUMMARY
    console.print(f"\n[bold]Sales — last {data['period_days']} days[/bold]")
    console.print(f"  Revenue: [green]£{data['revenue']:,.2f}[/green]")
    console.print(f"  Orders:  [cyan]{data['orders']:,}[/cyan]")
    console.print(f"  AOV:     [cyan]£{data['aov']:,.2f}[/cyan]")
    console.print(f"  Daily £: [cyan]{sparkline(data['daily_revenue'])}[/cyan]")

    render(
        data["top_products"],
        fmt="table",
        title="Top sellers",
        columns=["product_id", "name", "qty", "revenue"],
        numeric=["product_id", "qty"],
        money=["revenue"],
    )
    _console_err.print("\n[dim]This is canned demo data.[/dim]")


@app.command("doctor")
def doctor() -> None:
    """Simulate `opencart doctor` against a healthy store."""
    _console_err.print("\n[bold]Diagnosing profile:[/bold] [cyan]demo[/cyan]")
    _console_err.print("  Connection: [cyan]ssh[/cyan]\n")
    success("Connection: built SSHConnection")
    success("Shell exec: responsive")
    success("PHP: 8.2.18")
    success("MySQL: 8.0.45")
    success("OpenCart tables: found (oc_product exists)")
    success("OpenCart version: 3.x")
    _console_err.print("")
    success("All checks passed.")


@app.command("all")
def all_demos(
    pause: float = typer.Option(2.0, "--pause", help="Seconds between demos."),
) -> None:
    """Walk through every demo. Used by the README GIF recording."""
    _console_err.print("\n[bold cyan]opencart-cli demo[/bold cyan]\n")
    time.sleep(pause / 2)

    _console_err.print("[bold]$ opencart doctor[/bold]")
    doctor()
    time.sleep(pause)

    _console_err.print("\n[bold]$ opencart stock low --threshold 5[/bold]")
    products()
    time.sleep(pause)

    _console_err.print("\n[bold]$ opencart sales summary --days 7[/bold]")
    sales()
    time.sleep(pause)

    _console_err.print("\n[bold]$ opencart orders list --days 1[/bold]")
    orders()
    time.sleep(pause / 2)

    _console_err.print(
        "\n[bold green]✓ That's opencart-cli.[/bold green] "
        "Install with [cyan]pip install opencart-cli[/cyan] and run [cyan]opencart init[/cyan]."
    )


def _ensure_not_real_query(*_args, **_kwargs):
    """Safety net — should never be called in demo mode."""
    error("Demo command tried to hit a real database. This is a bug; please report.")
    raise typer.Exit(2)
