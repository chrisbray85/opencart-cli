"""Dry-run and confirmation helpers for mutation commands.

Every mutation command should run user input through `confirm_mutation()`:

  - `--dry-run` flag → print the planned change, exit without executing.
  - `--yes` flag → skip the interactive prompt.
  - default (interactive) → show the planned change, prompt y/N.

A consistent UX across every write command means users learn the safety
model once and trust it everywhere.
"""

from __future__ import annotations

import sys
from typing import Any

from rich.prompt import Confirm

from .formatters import _console_err, info, warn


def confirm_mutation(
    title: str,
    plan: dict[str, Any] | str,
    *,
    yes: bool,
    dry_run: bool,
) -> bool:
    """Show planned change and ask for confirmation.

    Returns True if the caller should proceed, False to abort.
    Exits with code 0 if dry-run was requested (success = "no action needed").
    """
    _console_err.print(f"\n[bold yellow]Plan:[/bold yellow] {title}")
    if isinstance(plan, dict):
        for k, v in plan.items():
            _console_err.print(f"  [cyan]{k}:[/cyan] {v}")
    else:
        _console_err.print(f"  {plan}")
    _console_err.print()

    if dry_run:
        info("Dry run — no changes made.")
        sys.exit(0)

    if yes:
        return True

    return Confirm.ask("Apply this change?", default=False)


def announce_skip(reason: str) -> None:
    """Print an explanation when a mutation can't proceed (e.g. read-only)."""
    warn(reason)
