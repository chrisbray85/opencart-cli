"""Per-invocation CLI context.

Holds the active profile, output format, and safety flags. Carried via
typer's `ctx.obj` so commands can pick what they need without each
command re-parsing global flags.
"""

from __future__ import annotations

from dataclasses import dataclass

from opencart_cli.core.config import Config, Profile
from opencart_cli.core.db import OpenCartDB, get_db

from .formatters import Format


@dataclass
class CLIContext:
    config: Config
    profile_override: str | None = None
    format: Format = "auto"
    yes: bool = False  # skip confirmations
    dry_run: bool = False  # show what would happen without doing it
    force_read_only: bool = False  # CLI flag forces read-only

    _profile: Profile | None = None
    _db: OpenCartDB | None = None

    def profile(self) -> Profile:
        if self._profile is None:
            p = self.config.get_profile(self.profile_override)
            if self.force_read_only:
                p.read_only = True
            self._profile = p
        return self._profile

    def db(self) -> OpenCartDB:
        if self._db is None:
            self._db = get_db(self.profile())
        return self._db
