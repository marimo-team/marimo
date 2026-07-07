# Copyright 2026 Marimo. All rights reserved.
"""Dependency-ordered restore for cell-defined classes/functions.

A cached block may define classes and functions that reference each other
(and instances of each other). On a cache hit the block is skipped, so the
loader must reconstruct everything — and it must do so in dependency order,
or exec/unpickle hits a NameError / missing-class error.
"""

from __future__ import annotations

import linecache
import textwrap
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

from marimo._runtime.patches import (
    create_main_module,
    patch_main_module_context,
)
from marimo._save.cache import Cache
from marimo._save.hash import HashKey
from marimo._save.loaders import LazyLoader
from marimo._save.stores.file import FileStore

CELL_FILENAME = "__marimo__cell_dep_.py"


def _seed_linecache(src: str) -> None:
    linecache.cache[CELL_FILENAME] = (
        len(src),
        None,
        [line + "\n" for line in src.splitlines()],
        CELL_FILENAME,
    )


def _save_then_restart_restore(
    src: str,
    names: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Run `src` in a fresh kernel main module, cache its `names`, then
    simulate a kernel restart and restore into a brand-new main module.
    Returns the restored namespace.
    """
    monkeypatch.setattr(
        Cache, "_cell_filename", staticmethod(lambda: CELL_FILENAME)
    )
    _seed_linecache(src)

    loader = LazyLoader("t", store=FileStore(save_path=str(tmp_path)))
    key = HashKey(hash="dephash", cache_type="Pure")

    # Original run + save — all under a patched __main__ so instances of
    # cell-defined classes pickle against the right module.
    original = create_main_module(None, None)
    with patch_main_module_context(original):
        exec(compile(src, CELL_FILENAME, "exec"), original.__dict__)
        defs = {name: original.__dict__[name] for name in names}
        cache = Cache(
            defs=dict(defs),
            hash=key.hash,
            cache_type=key.cache_type,
            stateful_refs=set(),
            hit=False,
            meta={},
        )
        cache.update(dict(defs))
        assert loader.save_cache(cache)
        loader.flush()

    # Simulated restart: a fresh main module with none of the cell defs.
    restarted = create_main_module(None, None)
    with patch_main_module_context(restarted):
        loaded = loader.load_cache(key)
        assert loaded is not None, "cache failed to load after restart"
        loaded.restore(restarted.__dict__)
        return dict(restarted.__dict__)


def test_function_class_ordering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`Foo`'s body calls `foo()` at class-definition time, so `foo` must
    be reconstructed before `Foo`."""
    src = textwrap.dedent(
        """
        def foo():
            return 21

        class Foo:
            doubled = foo() * 2
        """
    ).strip()
    scope = _save_then_restart_restore(
        src, ["foo", "Foo"], tmp_path, monkeypatch
    )
    assert scope["foo"]() == 21
    assert scope["Foo"].doubled == 42


def test_instance_of_cell_class_restores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The caveat case: `_baz` is an instance of the cell-defined class
    `Bar`, so `Bar` must be materialized before `_baz` unpickles; `Foo`
    depends on both `Bar` (annotation) and `foo` (called in its body)."""
    src = textwrap.dedent(
        """
        class Bar:
            def __init__(self, x: int):
                self.x = x

        _baz = Bar(7)

        def foo():
            return _baz

        class Foo:
            bar: Bar = foo()
        """
    ).strip()
    scope = _save_then_restart_restore(
        src, ["Bar", "_baz", "foo", "Foo"], tmp_path, monkeypatch
    )

    assert scope["Bar"](7).x == 7
    assert scope["_baz"].x == 7
    assert isinstance(scope["_baz"], scope["Bar"])
    # foo returns the restored module-level _baz
    assert scope["foo"]() is scope["_baz"]
    # Foo.bar was computed as foo() at class-def time
    assert scope["Foo"].bar is scope["_baz"]
