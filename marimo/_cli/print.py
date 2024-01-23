# Copyright 2024 Marimo. All rights reserved.

# Print helpers


def green(text: str) -> str:
    return "\033[32m" + text + "\033[0m"


def orange(text: str) -> str:
    return "\033[33m" + text + "\033[0m"
