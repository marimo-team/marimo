# Copyright 2024 Marimo. All rights reserved.
from typing import Literal

from marimo._save.loaders.json import JsonLoader
from marimo._save.loaders.loader import Loader, LoaderPartial, LoaderType
from marimo._save.loaders.memory import MemoryLoader
from marimo._save.loaders.pickle import PickleLoader

LoaderKey = Literal["memory", "pickle", "json"]

PERSISTENT_LOADERS: dict[LoaderKey, LoaderType] = {
    "pickle": PickleLoader,
    "json": JsonLoader,
}

__all__ = [
    "PERSISTENT_LOADERS",
    "Loader",
    "LoaderKey",
    "LoaderPartial",
    "LoaderType",
    "MemoryLoader",
    "PickleLoader",
]
