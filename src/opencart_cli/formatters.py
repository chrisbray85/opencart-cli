"""Output formatters: TTY-aware tables, JSON/YAML/CSV, sparklines.

When stdout is a terminal we print rich tables with colour and Unicode
borders. When piped to a file or another command, output defaults to
plain JSON so `jq` and friends work seamlessly. The `--format` flag
overrides the default in either direction.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from collections.abc import Iterable, Sequence
from typing import Any, Literal

import yaml
from rich.console import Console
from rich.table import Table

Format = Literal["auto", "table", "json", "yaml", "csv"]

# Unicode sparkline characters (low → high)
_SPARK_CHARS = " ▁▂▃▄▅▆▇█"

_console = Console()
_console_err = Console(stderr=True)


# ---------- Top-level entry point ----------


def render(
    rows: list[dict[str, Any]] | dict[str, Any],
    *,
    fmt: Format = "auto",
    title: str | None = None,
    columns: Sequence[str] | None = None,
    numeric: Sequence[str] | None = None,
    money: Sequence[str] | None = None,
    sparkline_col: str | None = None,
) -> None:
    """Render data in the user's chosen format.

    Args:
        rows: list of dicts (table-shape) or a single dict.
        fmt: "auto" picks table when stdout is a TTY, else json.
        title: optional table heading.
        columns: explicit column order; defaults to dict keys order.
        numeric: columns to right-align in table mode.
        money: columns to format as money in table mode.
        sparkline_col: numeric column to also render as a sparkline at the end.
    """
    effective_fmt = _resolve_format(fmt)
    if effective_fmt == "json":
        _emit_json(rows)
    elif effective_fmt == "yaml":
        _emit_yaml(rows)
    elif effective_fmt == "csv":
        _emit_csv(rows)
    else:
        _emit_table(
            rows if isinstance(rows, list) else [rows] if rows else [],
            title=title,
            columns=columns,
            numeric=numeric or (),
            money=money or (),
            sparkline_col=sparkline_col,
        )


def _resolve_format(fmt: Format) -> Format:
    if fmt != "auto":
        return fmt
    return "table" if sys.stdout.isatty() else "json"


# ---------- Format-specific writers ----------


def _emit_json(data: Any) -> None:
    sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")


def _emit_yaml(data: Any) -> None:
    sys.stdout.write(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))


def _emit_csv(rows: list[dict[str, Any]] | dict[str, Any]) -> None:
    if isinstance(rows, dict):
        rows = [rows]
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: ("" if v is None else v) for k, v in r.items()})


def _emit_table(
    rows: list[dict[str, Any]],
    *,
    title: str | None,
    columns: Sequence[str] | None,
    numeric: Sequence[str],
    money: Sequence[str],
    sparkline_col: str | None,
) -> None:
    if not rows:
        _console.print("[dim]No results.[/dim]")
        return
    cols = list(columns) if columns else list(rows[0].keys())
    table = Table(title=title, show_lines=False, header_style="bold cyan")
    for col in cols:
        justify = "right" if col in numeric or col in money else "left"
        table.add_column(col, justify=justify, no_wrap=False)
    for r in rows:
        table.add_row(*[_fmt_cell(r.get(c), c, money) for c in cols])
    _console.print(table)
    if sparkline_col:
        values = _coerce_numeric_series([r.get(sparkline_col) for r in rows])
        if values:
            _console.print(
                f"[dim]{sparkline_col}:[/dim] [cyan]{sparkline(values)}[/cyan] "
                f"[dim](min {min(values):,.2f} · max {max(values):,.2f})[/dim]"
            )


def _fmt_cell(value: Any, col: str, money: Sequence[str]) -> str:
    if value is None:
        return "[dim]—[/dim]"
    if col in money:
        try:
            return f"£{float(value):,.2f}"
        except (TypeError, ValueError):
            return str(value)
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


# ---------- Sparkline ----------


def sparkline(values: Iterable[float]) -> str:
    """Render a sequence of numbers as a Unicode sparkline."""
    arr = list(values)
    if not arr:
        return ""
    lo = min(arr)
    hi = max(arr)
    if hi == lo:
        return _SPARK_CHARS[len(_SPARK_CHARS) // 2] * len(arr)
    rng = hi - lo
    last = len(_SPARK_CHARS) - 1
    return "".join(_SPARK_CHARS[int(round((v - lo) / rng * last))] for v in arr)


def _coerce_numeric_series(seq: Sequence[Any]) -> list[float]:
    out: list[float] = []
    for v in seq:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


# ---------- Status output helpers ----------


def info(msg: str) -> None:
    _console_err.print(f"[cyan]i[/cyan] {msg}")


def success(msg: str) -> None:
    _console_err.print(f"[green]✓[/green] {msg}")


def warn(msg: str) -> None:
    _console_err.print(f"[yellow]![/yellow] {msg}")


def error(msg: str) -> None:
    _console_err.print(f"[red]✗[/red] {msg}")


def heading(text: str) -> None:
    _console_err.print(f"\n[bold]{text}[/bold]")


# Re-export the console for commands that need fancy rendering
console = _console


def to_csv_string(rows: list[dict[str, Any]]) -> str:
    """Render rows as a CSV string (useful for snapshots and tests)."""
    if not rows:
        return ""
    buf = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: ("" if v is None else v) for k, v in r.items()})
    return buf.getvalue()
