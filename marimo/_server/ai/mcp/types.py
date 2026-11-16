# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TypeAlias

MCPToolValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | list["MCPToolValue"]
    | dict[str, "MCPToolValue"]
    | None
)
MCPToolArgs: TypeAlias = dict[str, MCPToolValue] | None
