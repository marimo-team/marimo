# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import marimo._save.cache as _cache_module  # prevent variable shadowing
from marimo._save.cache import MARIMO_CACHE_VERSION
from marimo._save.save import cache, lru_cache, persistent_cache

__all__ = [
    "MARIMO_CACHE_VERSION",
    "_cache_module",
    "cache",
    "lru_cache",
    "persistent_cache",
]
