# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

# Print helpers


def green(text: str) -> str:
    return "\033[32m" + text + "\033[0m"


def orange(text: str) -> str:
    return "\033[33m" + text + "\033[0m"


def red(text: str) -> str:
    return "\033[31m" + text + "\033[0m"
