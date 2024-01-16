# Copyright 2024 Marimo. All rights reserved.
import functools
from typing import Any

from marimo._runtime.context import get_context


@functools.wraps(input)
def input_override(prompt: str = "") -> str:
    assert (stdin := get_context().stdin) is not None
    return stdin._readline_with_prompt(prompt)
