"""`opencart shell` — interactive REPL with persistent SSH/DDEV connection.

Commands typed in the shell are dispatched through the main typer app, so
anything you can run on the CLI works in the shell:

  oc> products list --low-stock-under 5
  oc> orders get 12345
  oc> sales summary
  oc> sql SELECT COUNT(*) FROM oc_customer
  oc> ask how many orders today

Special commands (REPL-only):
  oc> .help          show available top-level commands
  oc> .profile [n]   show or switch the active profile
  oc> .clear         clear the screen
  oc> .exit / .q     leave the shell (or Ctrl-D)
"""

from __future__ import annotations

import shlex
from collections.abc import Iterable

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from opencart_cli.context import CLIContext
from opencart_cli.core.config import config_dir
from opencart_cli.formatters import _console_err, error, info, success

# Top-level commands users can type in the shell
_TOP_LEVEL = [
    "products",
    "orders",
    "customers",
    "settings",
    "stock",
    "sales",
    "sql",
    "ask",
    "doctor",
    "profile",
    "watch",
]

# Common subcommands to seed autocomplete
_SUBCOMMANDS = {
    "products": ["list", "get", "update"],
    "orders": ["list", "get"],
    "customers": ["list"],
    "settings": ["list", "set"],
    "stock": ["low"],
    "sales": ["summary", "daily"],
    "profile": ["list", "use", "show", "remove"],
}


def run(
    ctx: typer.Context,
    profile_arg: str = typer.Option(
        None, "--profile", "-p", help="Override profile for this shell session."
    ),
) -> None:
    """Launch the interactive shell with a persistent connection."""
    cli: CLIContext = ctx.obj
    if profile_arg:
        cli.profile_override = profile_arg

    # Force-resolve profile + db now so the connection lives for the whole session
    try:
        profile = cli.profile()
        cli.db()  # eager connect — warms the SSH transport
    except Exception as e:
        error(f"Could not open session: {e}")
        raise typer.Exit(1) from e

    info(f"Connected: [cyan]{profile.name}[/cyan] ({profile.connection_type})")
    _console_err.print("[dim]Type a command, or '.help' for help. Ctrl-D to exit.[/dim]\n")

    history_file = config_dir() / "shell-history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    style = Style.from_dict({"prompt": "ansigreen bold"})
    session: PromptSession[str] = PromptSession(
        history=FileHistory(str(history_file)),
        completer=WordCompleter(_completion_words(), ignore_case=True, sentence=True),
        style=style,
    )

    # Lazy import to keep startup snappy and avoid circular import
    from opencart_cli.app import app as cli_app

    while True:
        try:
            line = session.prompt(f"oc[{profile.name}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            _console_err.print("[dim]bye 👋[/dim]")
            return

        if not line:
            continue

        if line.startswith("."):
            if _handle_repl_command(line, cli):
                # profile may have changed; refresh
                profile = cli.profile()
                continue
            else:
                return  # .exit / .q

        # Dispatch through the main typer app
        try:
            argv = shlex.split(line)
        except ValueError as e:
            error(f"Parse error: {e}")
            continue
        try:
            cli_app(args=argv, standalone_mode=False, obj=cli)
        except SystemExit:
            pass  # commands call typer.Exit which we swallow in REPL
        except typer.Exit:
            pass
        except Exception as e:
            error(str(e))


def _handle_repl_command(line: str, cli: CLIContext) -> bool:
    """Handle a .meta command. Returns True to keep looping, False to exit."""
    parts = line.split()
    cmd = parts[0]
    args = parts[1:]

    if cmd in (".exit", ".q", ".quit"):
        _console_err.print("[dim]bye 👋[/dim]")
        return False
    if cmd == ".help":
        _console_err.print(
            "\n[bold]Top-level commands:[/bold] "
            + ", ".join(_TOP_LEVEL)
            + "\n[bold]REPL commands:[/bold] .help, .profile [name], .clear, .exit"
        )
        return True
    if cmd == ".clear":
        print("\033[2J\033[H", end="")
        return True
    if cmd == ".profile":
        if not args:
            _console_err.print(
                f"[cyan]{cli.profile().name}[/cyan] ({cli.profile().connection_type})"
            )
            return True
        new_name = args[0]
        if new_name not in cli.config.profiles:
            error(f"No such profile: {new_name}")
            return True
        cli.profile_override = new_name
        cli._profile = None  # force re-resolve
        cli._db = None
        cli.db()  # warm the new connection
        success(f"Switched to profile {new_name}")
        return True
    error(f"Unknown REPL command: {cmd}. Try .help")
    return True


def _completion_words() -> Iterable[str]:
    words = list(_TOP_LEVEL)
    for cmd, subs in _SUBCOMMANDS.items():
        for sub in subs:
            words.append(f"{cmd} {sub}")
    words.extend([".help", ".profile", ".clear", ".exit", ".quit"])
    return words
