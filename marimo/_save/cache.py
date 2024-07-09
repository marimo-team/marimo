# Copyright 2024 Marimo. All rights reserved.

import re
from collections import namedtuple
from dataclasses import dataclass
from typing import Literal

from marimo._runtime.context import get_context

# Easy visual identification of cache type.
CACHE_PREFIX = {
    "ContentAddressed": "C_",
    "ExecutionPath": "E_",
    "Unknown": "U_",
}

CacheType = Literal["ContentAddressed", "ExecutionPath"]


def contextual_defs(cache):
    private_prefix = f"_cell_{get_context().execution_context.cell_id}"
    return {
        (var, re.sub(r"^_", private_prefix, var)): value
        for var, value in cache.defs.items()
    }


@dataclass
class Cache:
    defs: dict
    hash: str
    cache_type: CacheType
    hit: bool


ValidCacheSha = namedtuple("ValidCacheSha", ("sha", "cache_type"))
