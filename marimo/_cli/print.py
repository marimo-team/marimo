# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any, cast

import click

if TYPE_CHECKING:
    from click import Command, Context, HelpFormatter

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
    return "\033[1m" + text + "\033[0m" if _USE_COLOR else text


def green(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    prefix = "\033[32m" if not bold else "\033[1;32m"
    return prefix + text + "\033[0m"


def bright_green(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    prefix = "\033[92m" if not bold else "\033[1;92m"
    return prefix + text + "\033[0m"


def yellow(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    prefix = "\033[33m" if not bold else "\033[1;33m"
    return prefix + text + "\033[0m"


def orange(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    prefix = "\033[33m" if not bold else "\033[1;33m"
    return prefix + text + "\033[0m"


def red(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    prefix = "\033[31m" if not bold else "\033[1;31m"
    return prefix + text + "\033[0m"


def cyan(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    prefix = "\033[94m" if not bold else "\033[1;94m"
    return prefix + text + "\033[0m"


def light_blue(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    prefix = "\033[96m" if not bold else "\033[1;96m"
    return prefix + text + "\033[0m"


def muted(text: str) -> str:
    # Use dark gray (37 is white, 2 is dim) which is more widely supported than 90
    return "\033[37;2m" + text + "\033[0m" if _USE_COLOR else text


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
    cmd: "Command", ctx: "Context", formatter: "HelpFormatter"
) -> None:
    """Write usage line with colored 'Usage:' label."""
    pieces = cmd.collect_usage_pieces(ctx)
    formatter.write_usage(
        ctx.command_path, " ".join(pieces), bright_green("Usage: ", bold=True)
    )


def _format_options(
    cmd: "Command", ctx: "Context", formatter: "HelpFormatter"
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


class ColoredCommand:
    """Click Command with colored help output (cargo-style)."""

    def format_usage(self, ctx: "Context", formatter: "HelpFormatter") -> None:
        _format_usage(self, ctx, formatter)  # type: ignore[arg-type]

    def format_options(self, ctx: "Context", formatter: "HelpFormatter") -> None:
        _format_options(self, ctx, formatter)  # type: ignore[arg-type]


class ColoredGroup:
    """Click Group with colored help output (cargo-style)."""

    def format_usage(self, ctx: "Context", formatter: "HelpFormatter") -> None:
        _format_usage(self, ctx, formatter)  # type: ignore[arg-type]

    def format_options(self, ctx: "Context", formatter: "HelpFormatter") -> None:
        _format_options(self, ctx, formatter)  # type: ignore[arg-type]
        # Click's MultiCommand.format_options calls format_commands internally,
        # so we must do the same since we're overriding the method completely
        self.format_commands(ctx, formatter)  # type: ignore[attr-defined]

    def format_commands(self, ctx: "Context", formatter: "HelpFormatter") -> None:
        """Write all commands with colored names."""
        commands = []
        for subcommand in self.list_commands(ctx):  # type: ignore[attr-defined]
            cmd = self.get_command(ctx, subcommand)  # type: ignore[attr-defined]
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


class _ColoredCommand(ColoredCommand, click.Command):
    """Concrete colored command class."""

    pass


class _ColoredGroup(ColoredGroup, click.Group):
    """Concrete colored group class."""

    command_class = _ColoredCommand


def get_colored_command_class() -> type:
    """Get ColoredCommand class that inherits from click.Command."""
    return _ColoredCommand


def get_colored_group_class() -> type:
    """Get ColoredGroup class that inherits from click.Group."""
    return _ColoredGroup
