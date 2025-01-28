# Copyright 2024 Marimo. All rights reserved.
from marimo._save.loaders.json import JsonLoader
from marimo._save.loaders.loader import Loader, LoaderPartial, LoaderType
from marimo._save.loaders.memory import MemoryLoader
from marimo._save.loaders.pickle import PickleLoader

PERSISTENT_LOADERS: dict[str, LoaderType] = {
    "pickle": PickleLoader,
    "json": JsonLoader,
}

__all__ = [
    "PERSISTENT_LOADERS",
    "Loader",
    "LoaderPartial",
    "LoaderType",
    "MemoryLoader",
    "PickleLoader",
]
