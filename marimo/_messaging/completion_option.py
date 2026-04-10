# Copyright 2026 Marimo. All rights reserved.
"""Specification of a code completion result"""

from __future__ import annotations

import msgspec


class CompletionOption(msgspec.Struct):
    # completed symbol name
    name: str
    # type of symbol
    type: str
    # docstring, type hint, or other info
    completion_info: str | None

    def __post_init__(self) -> None:
        # Remove trailing quotes because frontends may automatically add quotes
        self.name = self.name.rstrip('"').rstrip("'")
