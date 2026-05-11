# Contributing to opencart-cli

Thanks for your interest! Contributions are very welcome.

## Quick setup

```bash
git clone https://github.com/chrisbray85/opencart-cli.git
cd opencart-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,ai]"
```

## Running checks

```bash
ruff check src/                    # lint
ruff format src/                   # format
mypy src/                          # type-check (best-effort)
pytest                             # tests
```

## Before opening a PR

1. **Run `ruff check src/` and `ruff format src/`.** CI does this.
2. **Add tests for new behaviour.** Quick smoke tests against fixtures are better than nothing.
3. **Update the changelog.** Add a line under `## Unreleased` in `CHANGELOG.md`.
4. **Don't include credentials.** Check `git diff` before committing.
5. **Keep PRs focused.** One feature or fix per PR — easier to review and ship.

## Adding a new command

1. Create `src/opencart_cli/commands/<name>.py`. Use existing commands as templates.
2. If it's a resource with subcommands, export `app = typer.Typer(...)` and register subcommands.
3. If it's a top-level command, export a `run(ctx, ...)` function.
4. Wire it up in `src/opencart_cli/app.py` (the imports + `app.add_typer` / `app.command` calls).
5. Use `operations.<func>(db, ...)` for data access — keeps the operations layer reusable.
6. Use `formatters.render(...)` for output.

## Adding a connection backend

1. Subclass `Connection` in `src/opencart_cli/core/connection.py`.
2. Implement `exec_php_stdin`, `exec_command`, `read_file`, `write_file`, optionally `close`.
3. Add a backend config dataclass (like `SSHConfig`, `DDEVConfig`).
4. Register in `make_connection()`'s dispatcher.
5. Update `commands/init.py` to prompt for the new type.
6. Update README's "Connection backends" section.

## Reporting bugs

Open an issue with:
- What you ran
- What you expected
- What happened (full output if you can)
- Your `opencart doctor` output (redact host/user)
- Your `opencart --version`
- OpenCart version + connection backend (ssh/ddev/local)

## Code of conduct

Be kind. We're here to make OpenCart less painful.
