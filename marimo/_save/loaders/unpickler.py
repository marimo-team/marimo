# Copyright 2026 Marimo. All rights reserved.
"""Custom pickle.Unpickler that resolves `__main__` refs against a cell
namespace.

Pickle serializes a class reference as `(module, qualname)`. For
classes defined inside marimo cells the module is `"__main__"`, but
the interpreter's `sys.modules["__main__"]` is not the cell namespace
— so `pickle.loads` of a cell-defined class (or an instance of one)
fails with `AttributeError: Can't get attribute 'KAN' on <module
'__main__' ...>`.

`CellNamespaceUnpickler` overrides `find_class` to consult a
caller-supplied `glbls` dict (the cell namespace) before falling back
to the default `getattr(sys.modules[module], name)` resolution.
"""

from __future__ import annotations

import io
import pickle
from typing import Any

__all__ = [
    "CellNamespaceUnpickler",
    "pickle_load_with_namespace",
]


class CellNamespaceUnpickler(pickle.Unpickler):
    """Unpickler whose `find_class` prefers a cell namespace for
    `__main__` refs."""

    def __init__(self, file: io.IOBase, glbls: dict[str, Any] | None) -> None:
        super().__init__(file)
        self._glbls = glbls or {}

    def find_class(self, module: str, name: str) -> Any:
        if module == "__main__" and name in self._glbls:
            return self._glbls[name]
        return super().find_class(module, name)


def pickle_load_with_namespace(
    data: bytes,
    type_hint: str | None,
    glbls: dict[str, Any] | None,
) -> Any:
    """Deserialize *data* with `__main__` fallback into *glbls*.

    Drop-in replacement for `_pickle_load(data, type_hint)` from
    :mod:`marimo._save.stubs.lazy_stub`. When `glbls` is `None`,
    behaves exactly like `pickle.loads(data)`.
    """
    del type_hint  # signature parity with _pickle_load
    if glbls is None:
        return pickle.loads(data)
    return CellNamespaceUnpickler(io.BytesIO(data), glbls).load()
