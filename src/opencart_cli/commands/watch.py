"""`opencart watch orders` — live tail of new orders."""

from __future__ import annotations

import sys
import time
from datetime import datetime

import typer

from opencart_cli.context import CLIContext
from opencart_cli.formatters import _console_err, console, error


def run(
    ctx: typer.Context,
    target: str = typer.Argument("orders", help="What to watch: 'orders' (more coming)."),
    interval: int = typer.Option(30, "--interval", "-i", help="Poll interval in seconds."),
    bell: bool = typer.Option(True, "--bell/--no-bell", help="Ring terminal bell on new event."),
) -> None:
    """Poll for new orders and print them as they arrive."""
    cli: CLIContext = ctx.obj
    if target != "orders":
        error(f"Unknown watch target: {target!r}. Currently supports: orders")
        raise typer.Exit(1)

    db = cli.db()
    last_id = _max_order_id(db)
    _console_err.print(
        f"[bold]Watching orders[/bold] — poll every {interval}s · last_id={last_id} "
        f"· {datetime.now().strftime('%H:%M:%S')}"
    )
    _console_err.print("[dim]Press Ctrl+C to stop.[/dim]\n")

    try:
        while True:
            new_orders = db.query(
                """
                SELECT order_id, firstname, lastname, email, total, date_added,
                       payment_method, shipping_method
                FROM oc_order
                WHERE order_id > ?
                ORDER BY order_id ASC
                """,
                [last_id],
            )
            if new_orders:
                if bell:
                    sys.stdout.write("\a")
                    sys.stdout.flush()
                for o in new_orders:
                    console.print(
                        f"[green]●[/green] Order [bold]{o['order_id']}[/bold] "
                        f"[dim]{o['date_added']}[/dim]  "
                        f"[cyan]{o['firstname']} {o['lastname']}[/cyan]  "
                        f"[bold]£{float(o['total']):.2f}[/bold]  "
                        f"[dim]{o['email']}[/dim]  "
                        f"[dim]{o['payment_method']}[/dim]"
                    )
                    last_id = max(last_id, int(o["order_id"]))
            time.sleep(interval)
    except KeyboardInterrupt:
        _console_err.print("\n[dim]Stopped.[/dim]")
        raise typer.Exit(0) from None


def _max_order_id(db) -> int:
    rows = db.query("SELECT COALESCE(MAX(order_id), 0) AS max_id FROM oc_order")
    return int(rows[0]["max_id"]) if rows else 0
