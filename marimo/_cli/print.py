# Copyright 2023 Marimo. All rights reserved.

# Print helpers


def light_gray(text: str) -> str:
    return "\033[37m" + text + "\033[0m"


def orange(text: str) -> str:
    return "\033[33m" + text + "\033[0m"
