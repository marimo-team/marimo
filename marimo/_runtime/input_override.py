# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
import sys


@functools.wraps(input)
def input_override(prompt: str = "") -> str:
    # sys.stdin is overridden
    return sys.stdin._readline_with_prompt(prompt)  # type: ignore[attr-defined, no-any-return, union-attr]  # noqa: E501
