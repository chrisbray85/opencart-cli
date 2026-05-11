"""Render the demo output as a sharp, scalable SVG for the README.

Uses rich's `Console.save_svg()` — captures the exact terminal output
(colours, sparklines, table borders, money formatting) as an SVG that
renders crisply at any zoom level. No GIF compression, no Chrome needed.

Usage:
    python scripts/render_demo_svg.py        # writes demo.svg
    python scripts/render_demo_svg.py docs/  # writes docs/demo.svg
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Import canned data straight from the demo command — single source of truth
from opencart_cli.commands.demo import _SALES_SUMMARY
from opencart_cli.formatters import sparkline


def render() -> str:
    """Render the demo into a recording Console and return the SVG string."""
    console = Console(record=True, width=110)

    # Header
    console.print()
    console.print("[bold cyan]$ opencart sales summary --days 7[/bold cyan]")
    console.print()

    # Sales summary block (matches commands/sales.py output exactly)
    data = _SALES_SUMMARY
    console.print(f"[bold]Sales — last {data['period_days']} days[/bold]")
    console.print(f"  Revenue: [green]£{data['revenue']:,.2f}[/green]")
    console.print(f"  Orders:  [cyan]{data['orders']:,}[/cyan]")
    console.print(f"  AOV:     [cyan]£{data['aov']:,.2f}[/cyan]")
    console.print(f"  Daily £: [cyan]{sparkline(data['daily_revenue'])}[/cyan]")
    console.print()

    # Top sellers table
    table = Table(title="Top sellers", header_style="bold cyan", show_lines=False)
    table.add_column("product_id", justify="right")
    table.add_column("name")
    table.add_column("qty", justify="right")
    table.add_column("revenue", justify="right")
    for row in data["top_products"]:
        table.add_row(
            str(row["product_id"]),
            row["name"],
            str(row["qty"]),
            f"£{row['revenue']:,.2f}",
        )
    console.print(table)
    console.print()

    return console.export_svg(title="opencart-cli")


def main() -> int:
    out_dir = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path(".")
    out_path = out_dir if out_dir.suffix == ".svg" else out_dir / "demo.svg"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(), encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
