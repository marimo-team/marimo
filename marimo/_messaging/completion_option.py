# Copyright 2026 Marimo. All rights reserved.
"""Specification of a code completion result"""

from __future__ import annotations

from typing import Optional

import msgspec


class CompletionOption(msgspec.Struct):
    # completed symbol name
    name: str
    # type of symbol
    type: str
    # docstring, type hint, or other info
    completion_info: Optional[str]

    def __post_init__(self) -> None:
        # Remove trailing quotes because frontends may automatically add quotes
        self.name = self.name.rstrip('"').rstrip("'")
