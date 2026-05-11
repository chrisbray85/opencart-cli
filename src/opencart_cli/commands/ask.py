"""`opencart ask "..."` — natural-language queries via Claude or OpenAI.

The headline feature: ask in English, get SQL generated against the actual
OpenCart schema, see the SQL, confirm, run it, format the results.

Provider is picked by which API key is set:
  - ANTHROPIC_API_KEY → Claude (anthropic SDK)
  - OPENAI_API_KEY    → OpenAI (openai SDK)

Both providers are optional installs. `pip install opencart-cli[ai]` pulls
both. If neither key is set or neither SDK is installed, the command
prints a clear setup message.
"""

from __future__ import annotations

import json
import os

import typer
from rich.prompt import Confirm
from rich.syntax import Syntax

from opencart_cli.context import CLIContext
from opencart_cli.core import operations
from opencart_cli.formatters import _console_err, error, render

_SYSTEM_PROMPT = """You convert plain-English questions about an OpenCart e-commerce
database into SAFE SQL.

Rules:
1. Output ONLY a JSON object with two keys: "sql" (string) and "explanation" (string).
2. Generate ONE SELECT/SHOW/DESCRIBE statement only — no mutations, no DDL.
3. Use OpenCart conventions: tables prefixed `oc_`, language_id=1 for English text.
4. For products, JOIN oc_product (p) with oc_product_description (pd) on product_id.
5. For orders, USE oc_order; total/date_added are common columns.
6. Use LIMIT to keep result sets sensible (default 50 if user hasn't asked otherwise).
7. If the question can't be safely answered with one SELECT, return SQL: "" and
   put the reason in "explanation".

Compact schema follows. Use ONLY these tables/columns:
"""


def run(
    ctx: typer.Context,
    question: str = typer.Argument(..., help="Your question in natural language."),
    auto_run: bool = typer.Option(
        False, "--auto-run", "-y", help="Run the generated SQL without confirmation."
    ),
    provider: str | None = typer.Option(
        None, "--provider", help="Force 'claude' or 'openai' (default: auto-detect)."
    ),
) -> None:
    """Ask a question — generates SQL with schema context, runs after confirm."""
    cli: CLIContext = ctx.obj

    # Pick provider
    actual_provider, generate = _pick_provider(provider)

    # Build schema context
    db = cli.db()
    _console_err.print("[dim]Reading schema...[/dim]")
    schema = operations.schema_summary(db, max_cols=24)
    if not schema:
        error("Could not read schema. Run `opencart doctor` first.")
        raise typer.Exit(1)

    # Generate SQL
    _console_err.print(f"[dim]Asking {actual_provider}...[/dim]")
    try:
        result = generate(question, schema)
    except Exception as e:
        error(f"AI provider error: {e}")
        raise typer.Exit(1) from e

    sql = result.get("sql", "").strip()
    explanation = result.get("explanation", "").strip()

    if not sql:
        error(f"AI declined to generate SQL: {explanation or 'no reason given'}")
        raise typer.Exit(1)

    # Show plan
    _console_err.print()
    if explanation:
        _console_err.print(f"[bold]Explanation:[/bold] {explanation}")
    _console_err.print("[bold]Generated SQL:[/bold]")
    _console_err.print(Syntax(sql, "sql", theme="ansi_dark", word_wrap=True))
    _console_err.print()

    # Confirm
    if not (auto_run or cli.yes):
        if not Confirm.ask("Run this query?", default=True):
            error("Aborted.")
            raise typer.Exit(1)

    # Run
    try:
        rows = operations.safe_select(db, sql)
    except ValueError as e:
        error(f"Refused to run: {e}")
        raise typer.Exit(1) from e
    render(rows, fmt=cli.format, title=f"{len(rows)} rows")


# ---------- Provider plumbing ----------


def _pick_provider(forced: str | None) -> tuple[str, callable]:  # type: ignore[type-arg]
    has_claude_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai_key = bool(os.environ.get("OPENAI_API_KEY"))

    if forced:
        forced = forced.lower()
        if forced == "claude":
            return "Claude (Anthropic)", _generate_claude
        if forced == "openai":
            return "OpenAI", _generate_openai
        raise typer.BadParameter(f"Unknown provider: {forced!r}")

    if has_claude_key:
        return "Claude (Anthropic)", _generate_claude
    if has_openai_key:
        return "OpenAI", _generate_openai

    error(
        "No AI provider available. Set ANTHROPIC_API_KEY or OPENAI_API_KEY, "
        "and `pip install opencart-cli[ai]`."
    )
    raise typer.Exit(1)


def _generate_claude(question: str, schema: dict) -> dict:
    try:
        import anthropic  # type: ignore
    except ImportError as e:
        raise RuntimeError("anthropic SDK not installed. Run: pip install opencart-cli[ai]") from e

    client = anthropic.Anthropic()
    prompt = _SYSTEM_PROMPT + json.dumps(schema, separators=(",", ":"))
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=prompt,
        messages=[{"role": "user", "content": question}],
    )
    text = msg.content[0].text.strip()
    return _parse_json_block(text)


def _generate_openai(question: str, schema: dict) -> dict:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as e:
        raise RuntimeError("openai SDK not installed. Run: pip install opencart-cli[ai]") from e

    client = OpenAI()
    prompt = _SYSTEM_PROMPT + json.dumps(schema, separators=(",", ":"))
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": question},
        ],
    )
    text = resp.choices[0].message.content or "{}"
    return _parse_json_block(text)


def _parse_json_block(text: str) -> dict:
    """Strip optional code fences and parse JSON."""
    text = text.strip()
    if text.startswith("```"):
        # remove ```json ... ``` fences
        lines = text.splitlines()
        text = "\n".join(line for line in lines if not line.startswith("```"))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract first {...} block as a fallback
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"sql": "", "explanation": f"could not parse AI response: {text[:200]}"}
