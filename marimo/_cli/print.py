# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import os
import sys
from typing import Any, cast

import click

from marimo._config.settings import GLOBAL_SETTINGS


# Check if we're on Windows and if ANSI colors are supported
def _supports_color() -> bool:
    if os.environ.get("NO_COLOR") == "1":
        return False

    # Windows 10 build 14931+ supports ANSI color codes
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            # Get Windows version
            major = sys.getwindowsversion().major  # type: ignore[attr-defined]
            build = sys.getwindowsversion().build  # type: ignore[attr-defined]

            # Check if Windows 10+ and if VIRTUAL_TERMINAL_PROCESSING is enabled
            return cast(
                bool,
                major >= 10
                and build >= 14931
                and kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7),  # type: ignore[attr-defined]
            )
        except Exception:
            return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


_USE_COLOR = _supports_color()


def bold(text: str) -> str:
    return click.style(text, bold=True) if _USE_COLOR else text


def green(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    return click.style(text, fg="green", bold=bold)


def bright_green(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    return click.style(text, fg="bright_green", bold=bold)


def yellow(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    return click.style(text, fg="yellow", bold=bold)


def orange(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    return click.style(text, fg="yellow", bold=bold)


def red(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    return click.style(text, fg="red", bold=bold)


def cyan(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    return click.style(text, fg="bright_blue", bold=bold)


def light_blue(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    return click.style(text, fg="bright_cyan", bold=bold)


def muted(text: str) -> str:
    return click.style(text, fg="white", dim=True) if _USE_COLOR else text


def _echo_or_print(*args: Any, **kwargs: Any) -> None:
    try:
        import click

        click.echo(*args, **kwargs)
    except ModuleNotFoundError:
        print(*args, **kwargs)  # noqa: T201


def echo(*args: Any, **kwargs: Any) -> None:
    if GLOBAL_SETTINGS.QUIET:
        return

    try:
        _echo_or_print(*args, **kwargs)  # noqa: T201
    except UnicodeEncodeError:
        # Handle non-UTF-8 terminals (such as CP-1252, Windows) by replacing
        # common Unicode characters with ASCII equivalents for non-UTF-8
        # terminals.
        ascii_args = []
        for arg in args:
            if isinstance(arg, str):
                ascii_arg = arg.replace("→", "->").replace("←", "<-")
                ascii_arg = ascii_arg.replace("✓", "v").replace("✗", "x")
                ascii_arg = ascii_arg.replace("•", "*").replace("…", "...")
                ascii_args.append(ascii_arg)
            else:
                ascii_args.append(arg)
        _echo_or_print(*ascii_args, **kwargs)


# --- Colored Click classes for CLI help formatting ---
# These follow cargo's color conventions:
# - Bold bright green for section headers (Usage:, Options:, Commands:)
# - Bold bright cyan for command/option names


def _format_usage(
    cmd: click.Command, ctx: click.Context, formatter: click.HelpFormatter
) -> None:
    """Write usage line with colored 'Usage:' label."""
    pieces = cmd.collect_usage_pieces(ctx)
    formatter.write_usage(
        ctx.command_path, " ".join(pieces), bright_green("Usage: ", bold=True)
    )


def _format_options(
    cmd: click.Command, ctx: click.Context, formatter: click.HelpFormatter
) -> None:
    """Write all options with colored names."""
    opts = []
    for param in cmd.get_params(ctx):
        rv = param.get_help_record(ctx)
        if rv is not None:
            opts.append(rv)

    if opts:
        rows = [(light_blue(opt, bold=True), desc) for opt, desc in opts]
        with formatter.section(bright_green("Options", bold=True)):
            formatter.write_dl(rows)


class ColoredCommand(click.Command):
    """Click Command with colored help output (cargo-style)."""

    def format_usage(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        _format_usage(self, ctx, formatter)

    def format_options(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        _format_options(self, ctx, formatter)


class ColoredGroup(click.Group):
    """Click Group with colored help output (cargo-style)."""

    command_class = ColoredCommand

    def format_usage(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        _format_usage(self, ctx, formatter)

    def format_options(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        _format_options(self, ctx, formatter)
        # Click's MultiCommand.format_options calls format_commands internally,
        # so we must do the same since we're overriding the method completely
        self.format_commands(ctx, formatter)

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Write all commands with colored names."""
        commands = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None or cmd.hidden:
                continue
            commands.append((subcommand, cmd))

        if commands:
            rows = [
                (light_blue(subcommand, bold=True), cmd.get_short_help_str())
                for subcommand, cmd in commands
            ]
            with formatter.section(bright_green("Commands", bold=True)):
                formatter.write_dl(rows)
