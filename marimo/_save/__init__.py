# Copyright 2024 Marimo. All rights reserved.
import marimo._save.cache as _cache_module  # prevent variable shadowing
from marimo._save.cache import MARIMO_CACHE_VERSION
from marimo._save.save import cache, lru_cache, persistent_cache

__all__ = [
    "cache",
    "lru_cache",
    "persistent_cache",
    "MARIMO_CACHE_VERSION",
    "_cache_module",
]
