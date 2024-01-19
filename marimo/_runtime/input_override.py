# Copyright 2024 Marimo. All rights reserved.
import functools
import sys


@functools.wraps(input)
def input_override(prompt: str = "") -> str:
    # sys.stdin is overridden
    return sys.stdin._readline_with_prompt(prompt)  # type: ignore[attr-defined, no-any-return]  # noqa: E501
