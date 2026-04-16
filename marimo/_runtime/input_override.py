# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
import sys
from typing import Any


@functools.wraps(input)
def input_override(prompt: str = "") -> str:
    # sys.stdin is overridden
    return sys.stdin._readline_with_prompt(prompt)  # type: ignore[attr-defined, no-any-return, union-attr]


def getpass_override(prompt: str = "Password: ", stream: Any = None) -> str:
    """Override for getpass.getpass that routes through marimo's stdin.

    The stream parameter is accepted for API compatibility but ignored,
    matching ipykernel's behavior.
    """
    del stream
    return sys.stdin._readline_with_prompt(prompt, password=True)  # type: ignore[attr-defined, no-any-return, union-attr]
