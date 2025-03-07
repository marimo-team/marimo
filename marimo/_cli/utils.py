# Copyright 2024 Marimo. All rights reserved.

from pathlib import Path
from sys import stdin

from marimo._config.settings import GLOBAL_SETTINGS


def prompt_to_overwrite(path: Path) -> bool:
    if GLOBAL_SETTINGS.YES:
        return False

    # Check if not in an interactive terminal
    # default to False
    if not stdin.isatty():
        return False

    if path.exists():
        return True

    return False
