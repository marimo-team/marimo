# Copyright 2026 Marimo. All rights reserved.
#
# Colored Click classes for CLI help formatting.
#
# These follow cargo's color conventions:
# - Bold bright green for section headers (Usage:, Options:, Commands:)
# - Bold bright cyan for command/option names

from __future__ import annotations

import click

from marimo._cli.print import bright_green, light_blue


class ColoredCommand(click.Command):
    """Click Command with colored help output (cargo-style)."""

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
