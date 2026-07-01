# Copyright 2026 Marimo. All rights reserved.
"""End-to-end: a cell-defined class survives a cache save/restore cycle as
a usable class (not a leftover ClassStub) through both the pickle and lazy
loaders.

This is the behavior behind `with mo.persistent_cache(...): class Foo: ...`
— on a cache hit the second run must restore `Foo` as a real class so
`Foo()` / `isinstance(..., Foo)` work.
"""

from __future__ import annotations

import linecache
from typing import Any

import pytest

from marimo._save.cache import Cache
from marimo._save.loaders import LazyLoader, PickleLoader
from marimo._save.stores.file import FileStore

CELL_FILENAME = "__marimo__cell_RtRt_.py"

# Source for a fake marimo cell defining three flavors of class.
CELL_SRC = (
    "class WithMethod:\n"
    "    def __init__(self, v: int = 0) -> None:\n"
    "        self.v = v\n"
    "\n"
    "    def doubled(self) -> int:\n"
    "        return self.v * 2\n"
    "\n"
    "class OnlyStatic:\n"
    "    @staticmethod\n"
    "    def f() -> int:\n"
    "        return 7\n"
    "\n"
    "class JustAttrs:\n"
    "    x = 1\n"
)


@pytest.fixture
def cell_namespace() -> dict[str, Any]:
    linecache.cache[CELL_FILENAME] = (
        len(CELL_SRC),
        None,
        [line + "\n" for line in CELL_SRC.splitlines()],
        CELL_FILENAME,
    )
    glbls: dict[str, Any] = {"__name__": "__main__"}
    exec(compile(CELL_SRC, CELL_FILENAME, "exec"), glbls)
    yield glbls
    linecache.cache.pop(CELL_FILENAME, None)


def _make_loader(kind: str, save_path: str):
    store = FileStore(save_path=save_path)
    if kind == "pickle":
        return PickleLoader("test", store=store)
    return LazyLoader("test", store=store)


def _round_trip(loader: Any, cache: Cache) -> Cache:
    """Persist `cache` through `loader` and read it back."""
    if isinstance(loader, PickleLoader):
        blob = loader.to_blob(cache)
        return loader.restore_cache(cache.key, blob)
    # LazyLoader writes blobs on a background thread.
    assert loader.save_cache(cache)
    loader.flush()
    loaded = loader.load_cache(cache.key)
    assert loaded is not None
    return loaded


@pytest.mark.parametrize("kind", ["pickle", "lazy"])
@pytest.mark.parametrize("var", ["WithMethod", "OnlyStatic", "JustAttrs"])
def test_class_round_trip(
    kind: str,
    var: str,
    cell_namespace: dict[str, Any],
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cls = cell_namespace[var]
    # Simulate the runtime context's cell filename so attribute-only
    # classes (no method code object) source from linecache.
    monkeypatch.setattr(
        Cache, "_cell_filename", staticmethod(lambda: CELL_FILENAME)
    )

    cache = Cache(
        defs={var: cls},
        hash="classhash",
        cache_type="Pure",
        stateful_refs=set(),
        hit=False,
        meta={},
    )
    cache.update({var: cls})
    # The class was converted to a ClassStub for serialization.
    from marimo._save.stubs import ClassStub

    assert isinstance(cache.defs[var], ClassStub)

    loader = _make_loader(kind, str(tmp_path))
    loaded = _round_trip(loader, cache)

    scope: dict[str, Any] = {"__name__": "__main__"}
    loaded.restore(scope)

    restored = scope[var]
    assert isinstance(restored, type), (
        f"{var} restored as {type(restored)}, expected a class"
    )
    if var == "WithMethod":
        assert restored(5).doubled() == 10
    elif var == "OnlyStatic":
        assert restored.f() == 7
    else:
        assert restored.x == 1
