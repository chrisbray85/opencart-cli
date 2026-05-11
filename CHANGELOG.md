# Changelog

All notable changes to `opencart-cli` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [1.0.0] — Initial release

### Added
- **`opencart ask "..."`** — natural-language queries powered by Claude or OpenAI. Generates SQL with schema context, shows you the query, then runs it.
- **`opencart shell`** — interactive REPL with persistent SSH connection, command history, and autocomplete.
- **`opencart watch orders`** — real-time order tail with terminal bell notifications.
- **`opencart doctor`** — diagnoses SSH, MySQL, OpenCart install, common misconfigurations.
- **Multi-profile config** — manage multiple OpenCart stores from one CLI. `opencart init` wizard sets you up in 60 seconds.
- **OS keychain integration** — database passwords stored in macOS Keychain / Linux Secret Service / Windows Credential Manager. Never in plaintext config.
- **Resource commands**: `products`, `orders`, `customers`, `settings`, `stock`, `sales`, `categories`, `seo`, `info`.
- **Safety rails**: dry-run by default on mutations, `--read-only` mode, audit log of every change.
- **Output formats**: TTY-aware tables (sparklines included), `--format=json|yaml|csv` for scripting.
- **Connection pooling** — single persistent SSH per profile, dramatic latency reduction.
- **Shell completions** — bash, zsh, fish, PowerShell.
- **`opencart sql`** — raw SQL escape hatch with safety guards.

### Performance
- Persistent SSH connection drops typical command latency from ~1.5s to ~50ms.

### Security
- Parameterised SQL throughout — no string interpolation of credentials or user input.
- DB passwords never written to config file when keyring is available.
- Read-only mode auto-enabled for profiles named `prod*` by default.
