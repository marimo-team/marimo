# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from collections import namedtuple
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from marimo._runtime.context import get_context

if TYPE_CHECKING:
    from marimo._ast.visitor import Name

CacheType = Literal["ContentAddressed", "ExecutionPath", "Unknown"]
# Easy visual identification of cache type.
CACHE_PREFIX: dict[CacheType, str] = {
    "ContentAddressed": "C_",
    "ExecutionPath": "E_",
    "Unknown": "U_",
}

ValidCacheSha = namedtuple("ValidCacheSha", ("sha", "cache_type"))


@dataclass
class Cache:
    defs: dict[Name, Any]
    hash: str
    cache_type: CacheType
    hit: bool


def contextual_defs(cache: Cache) -> dict[tuple[Name, Name], Any]:
    """Uses context to resolve private variable names."""
    context = get_context().execution_context
    assert context is not None, "Context could not be resolved"
    private_prefix = f"_cell_{context.cell_id}_"
    return {
        (var, re.sub(r"^_", private_prefix, var)): value
        for var, value in cache.defs.items()
    }
