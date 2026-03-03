# Copyright 2026 Marimo. All rights reserved.
#
# Colored Click classes for CLI help formatting.
#
# These follow cargo's color conventions:
# - Bold bright green for section headers (Usage:, Options:, Commands:)
# - Bold bright cyan for command/option names

from __future__ import annotations

import click
from click.utils import make_str

from marimo._cli.print import bright_green, light_blue
from marimo._cli.suggestions import suggest_commands, suggest_short_options


def _split_option_token(token: str) -> tuple[str, str]:
    """Split option-like tokens without depending on click's private parser."""
    first = token[:1]
    if first.isalnum():
        return "", token
    if token[1:2] == first:
        return token[:2], token[2:]
    return first, token[1:]


def _collect_short_options(
    command: click.Command, ctx: click.Context
) -> list[str]:
    """Collect all short flag names (e.g. -p) declared on a command."""
    options: set[str] = set()
    for param in command.get_params(ctx):
        if not isinstance(param, click.Option):
            continue
        for option in [*param.opts, *param.secondary_opts]:
            if option.startswith("-") and not option.startswith("--"):
                options.add(option)
    return sorted(options)


def _augment_short_option_error(
    command: click.Command,
    ctx: click.Context,
    error: click.NoSuchOption,
) -> None:
    """Populate click's possibilities for misspelled short flags."""
    if error.possibilities:
        return
    if not error.option_name.startswith("-") or error.option_name.startswith(
        "--"
    ):
        return

    short_options = _collect_short_options(command, ctx)
    suggestions = suggest_short_options(error.option_name, short_options)
    if suggestions:
        error.possibilities = suggestions


class ColoredCommand(click.Command):
    """Click Command with colored help output (cargo-style)."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except click.NoSuchOption as error:
            _augment_short_option_error(self, ctx, error)
            raise

    def format_usage(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        pieces = self.collect_usage_pieces(ctx)
        formatter.write_usage(
            ctx.command_path,
            " ".join(pieces),
            bright_green("Usage: ", bold=True),
        )

    def format_options(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        opts = []
        for param in self.get_params(ctx):
            rv = param.get_help_record(ctx)
            if rv is not None:
                opts.append(rv)

        if opts:
            rows = [(light_blue(opt, bold=True), desc) for opt, desc in opts]
            with formatter.section(bright_green("Options", bold=True)):
                formatter.write_dl(rows)


class ColoredGroup(click.Group):
    """Click Group with colored help output (cargo-style)."""

    command_class = ColoredCommand

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except click.NoSuchOption as error:
            _augment_short_option_error(self, ctx, error)
            raise

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        """Resolve subcommands and emit close-match suggestions on typos."""
        cmd_name = make_str(args[0])
        original_cmd_name = cmd_name

        cmd = self.get_command(ctx, cmd_name)
        if cmd is None and ctx.token_normalize_func is not None:
            cmd_name = ctx.token_normalize_func(cmd_name)
            cmd = self.get_command(ctx, cmd_name)

        if cmd is None and not ctx.resilient_parsing:
            if _split_option_token(cmd_name)[0]:
                self.parse_args(ctx, args)

            command_names: list[str] = []
            for name in self.list_commands(ctx):
                command = self.get_command(ctx, name)
                if command is None or command.hidden:
                    continue
                command_names.append(name)
            suggestions = suggest_commands(original_cmd_name, command_names)
            if len(suggestions) == 1:
                ctx.fail(
                    f"unrecognized command {original_cmd_name!r}\n\n"
                    f"  tip: a similar command exists: {suggestions[0]!r}"
                )
            if len(suggestions) > 1:
                joined = ", ".join(repr(item) for item in suggestions)
                ctx.fail(
                    f"unrecognized command {original_cmd_name!r}\n\n"
                    f"  tip: some similar commands exist: {joined}"
                )
            ctx.fail(f"unrecognized command {original_cmd_name!r}")

        return cmd_name if cmd else None, cmd, args[1:]

    def format_usage(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        pieces = self.collect_usage_pieces(ctx)
        formatter.write_usage(
            ctx.command_path,
            " ".join(pieces),
            bright_green("Usage: ", bold=True),
        )

    def format_options(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        opts = []
        for param in self.get_params(ctx):
            rv = param.get_help_record(ctx)
            if rv is not None:
                opts.append(rv)

        if opts:
            rows = [(light_blue(opt, bold=True), desc) for opt, desc in opts]
            with formatter.section(bright_green("Options", bold=True)):
                formatter.write_dl(rows)

        # Click's MultiCommand.format_options calls format_commands
        # internally, so we must do the same since we're overriding
        # the method completely
        self.format_commands(ctx, formatter)

    def format_commands(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        """Write all commands with colored names."""
        commands = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None or cmd.hidden:
                continue
            commands.append((subcommand, cmd))

        if commands:
            rows = [
                (
                    light_blue(subcommand, bold=True),
                    cmd.get_short_help_str(),
                )
                for subcommand, cmd in commands
            ]
            with formatter.section(bright_green("Commands", bold=True)):
                formatter.write_dl(rows)
