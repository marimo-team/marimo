# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import click

from marimo._cli.install_hints import get_install_commands
from marimo._cli.print import bold, green, muted, red


class MarimoCLIError(click.ClickException):
    """Base class for marimo CLI errors."""

    def show(self, file: Any = None) -> None:
        if file is None:
            file = click.get_text_stream("stderr")

        ctx = getattr(self, "ctx", None)
        color = ctx.color if ctx is not None else None
        click.echo(
            f"{red('Error', bold=True)}: {self.format_message()}",
            file=file,
            color=color,
        )


class MarimoCLIRuntimeError(MarimoCLIError):
    """Raised for runtime or environment setup failures."""


class MarimoCLIMissingDependencyError(MarimoCLIError):
    """Raised when a required dependency is unavailable."""

    def __init__(
        self,
        message: str,
        packages: str | list[str] | tuple[str, ...],
        *,
        additional_tip: str | None = None,
        followup_commands: str | list[str] | tuple[str, ...] | None = None,
        followup_label: str = "Then run:",
    ) -> None:
        """Build a dependency error message with install and follow-up hints."""
        package_spec: str | list[str]
        if isinstance(packages, str):
            package_spec = packages
        else:
            package_spec = list(packages)

        commands = get_install_commands(package_spec)
        lines = [message]

        if commands:
            primary_install = commands[0]
            lines.extend(
                [
                    "",
                    f"  {green('Tip:')} Install with:",
                    "",
                    f"    {primary_install}",
                ]
            )
            if len(commands) > 1:
                pip_install = commands[1]
                lines.extend(
                    [
                        "",
                        f"  {muted('Or with pip:')}",
                        "",
                        f"    {pip_install}",
                    ]
                )

        followup: list[str]
        if followup_commands is None:
            followup = []
        elif isinstance(followup_commands, str):
            command = followup_commands.strip()
            followup = [command] if command else []
        else:
            followup = [
                command.strip()
                for command in followup_commands
                if command.strip()
            ]

        if followup:
            primary_followup = followup[0]
            lines.extend(
                [
                    "",
                    f"  {green('Tip:')} {followup_label.strip()}",
                    "",
                    f"    {bold(primary_followup)}",
                ]
            )
            if len(followup) > 1:
                fallback_followup = followup[1]
                lines.extend(
                    [
                        "",
                        f"  {muted('Or with fallback:')}",
                        "",
                        f"    {bold(fallback_followup)}",
                    ]
                )

        if additional_tip:
            lines.extend(["", f"  {additional_tip.strip()}"])

        super().__init__("\n".join(lines))
