# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import urllib.parse
from typing import Optional, Union


def flatten_string(text: str) -> str:
    return "".join([line.strip() for line in text.split("\n")])


def create_style(
    pairs: dict[str, Union[str, int, float, None]],
) -> Optional[str]:
    if not pairs:
        return None

    return ";".join([f"{k}: {v}" for k, v in pairs.items() if v is not None])


def uri_encode_component(code: str) -> str:
    """Equivalent to `encodeURIComponent` in JavaScript."""
    return urllib.parse.quote(code, safe="~()*!.'")


def uri_decode_component(code: str) -> str:
    """Equivalent to `decodeURIComponent` in JavaScript."""
    return urllib.parse.unquote(code)


def normalize_dimension(value: Union[int, float, str, None]) -> Optional[str]:
    """Normalize dimension value to CSS string.

    Handles:
    - Integers (converted to px)
    - Strings (passed through if they have units, converted to px if just number)
    - None (returns None)
    """
    if value is None:
        return None
    if isinstance(value, int):
        return f"{value}px"
    if isinstance(value, float):
        return f"{value}px"
    if isinstance(value, str):
        # If string is just a number, treat as percentage
        if value.isdigit():
            return f"{value}px"
        return value
    raise ValueError(f"Invalid dimension value: {value}")
