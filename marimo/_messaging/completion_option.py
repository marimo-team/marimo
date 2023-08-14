# Copyright 2023 Marimo. All rights reserved.
"""Specification of a code completion result
"""


from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CompletionOption:
    # completed symbol name
    name: str
    # type of symbol
    type: str
    # docstring, type hint, or other info
    completion_info: Optional[str]
