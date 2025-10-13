# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from sys import stdout
from typing import TYPE_CHECKING

import click

from marimo._config.settings import GLOBAL_SETTINGS

if TYPE_CHECKING:
    from pathlib import Path


def prompt_to_overwrite(path: Path) -> bool:
    if GLOBAL_SETTINGS.YES:
        return True

    # Check if not in an interactive terminal
    # default to False
    if not stdout.isatty():
        return True

    if path.exists():
        return click.confirm(
            f"Warning: The file '{path}' already exists. Overwrite?",
            default=False,
        )

    return True
