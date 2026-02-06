# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys

import click

from marimo._cli.print import green


class MarimoCLIError(click.ClickException):
    """Base class for marimo CLI errors."""

    pass


def _infer_install_command() -> str:
    """Infer the package install command from sys.argv[0]."""
    argv0 = sys.argv[0] if sys.argv else ""
    if "conda" in argv0 or "mamba" in argv0:
        return "conda install"
    if "uv" in argv0:
        return "uv pip install"
    return "pip install"


class MarimoCLIMissingDependencyError(MarimoCLIError):
    """Raised when a required CLI dependency is not installed."""

    def __init__(
        self,
        message: str,
        package: str,
        *,
        additional_tip: str | None = None,
    ) -> None:
        install_cmd = _infer_install_command()
        lines = [
            f"{message}\n",
            f"  {green('Tip')}: Install with:\n",
            f"    {install_cmd} {package}\n",
        ]
        if additional_tip:
            lines.append(f"  {additional_tip}")
        super().__init__("\n".join(lines))
