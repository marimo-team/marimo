# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

from marimo._save.loaders.json import JsonLoader
from marimo._save.loaders.loader import (
    BasePersistenceLoader,
    Loader,
    LoaderPartial,
    LoaderType,
)
from marimo._save.loaders.memory import MemoryLoader
from marimo._save.loaders.pickle import PickleLoader

LoaderKey = Literal["memory", "pickle", "json"]

PERSISTENT_LOADERS: dict[LoaderKey, LoaderType] = {
    "pickle": PickleLoader,
    "json": JsonLoader,
}

__all__ = [
    "BasePersistenceLoader",
    "JsonLoader",
    "Loader",
    "LoaderKey",
    "LoaderPartial",
    "LoaderType",
    "MemoryLoader",
    "PERSISTENT_LOADERS",
    "PickleLoader",
]
