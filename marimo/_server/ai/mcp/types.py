# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TypeAlias

MCPToolValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | list["MCPToolValue"]
    | dict[str, "MCPToolValue"]
)
MCPToolArgs: TypeAlias = dict[str, MCPToolValue] | None
