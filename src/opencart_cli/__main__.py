"""Entry point: `python -m opencart_cli` or `opencart`.

Wraps the typer app with clean error handling for expected exceptions —
read-only refusals, connection failures, DB errors, config issues — so
users see a one-line error instead of a stack trace.
"""

import sys


def app() -> None:
    # Imports deferred so `opencart --help` is snappy.
    from opencart_cli.app import app as _typer_app
    from opencart_cli.core.config import ConfigError
    from opencart_cli.core.connection import ConnectionFailed
    from opencart_cli.core.db import DBError, ReadOnlyError
    from opencart_cli.formatters import error

    try:
        _typer_app()
    except KeyboardInterrupt:
        sys.exit(130)
    except (ReadOnlyError, ConnectionFailed, DBError, ConfigError) as e:
        error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    app()
