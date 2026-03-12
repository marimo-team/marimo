# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import click

from marimo._cli.print import red


def _normalize_usage_message(message: str) -> str:
    """Normalize usage text for concise lowercase error output."""
    message = message.strip()
    if message.endswith("."):
        message = message[:-1]
    if message and message[0].isupper():
        return message[0].lower() + message[1:]
    return message


def _format_suggestion_tip(suggestions: list[str]) -> str:
    suggestions = sorted(suggestions)
    if len(suggestions) == 1:
        return f"  tip: a similar argument exists: {suggestions[0]!r}"
    joined = ", ".join(repr(item) for item in suggestions)
    return f"  tip: some similar arguments exist: {joined}"


def _format_no_such_option(error: click.NoSuchOption) -> list[str]:
    lines = [
        f"{red('error')}: unexpected argument {error.option_name!r} found"
    ]
    if error.possibilities:
        lines.extend(["", _format_suggestion_tip(list(error.possibilities))])
    return lines


def _format_generic_usage_error(error: click.UsageError) -> list[str]:
    message_lines = error.format_message().splitlines()
    if not message_lines:
        return [f"{red('error')}: usage error"]

    first = _normalize_usage_message(message_lines[0])
    return [f"{red('error')}: {first}", *message_lines[1:]]


def _format_usage_error(error: click.UsageError) -> list[str]:
    if isinstance(error, click.NoSuchOption):
        return _format_no_such_option(error)
    return _format_generic_usage_error(error)


def show_compact_usage_error(
    error: click.UsageError, file: Any = None
) -> None:
    """Print compact parser errors without the full command help block."""
    if file is None:
        file = click.get_text_stream("stderr")

    color = error.ctx.color if error.ctx is not None else None
    for line in _format_usage_error(error):
        click.echo(line, file=file, color=color)

    if error.ctx is not None:
        click.echo(file=file, color=color)
        click.echo(error.ctx.get_usage(), file=file, color=color)
        click.echo(file=file, color=color)

    click.echo(
        "For more information, try '--help'.",
        file=file,
        color=color,
    )
