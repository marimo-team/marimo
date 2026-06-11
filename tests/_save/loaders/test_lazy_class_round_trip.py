# Copyright 2026 Marimo. All rights reserved.
"""End-to-end LazyLoader round-trip for cell-defined classes.

These tests mimic the failing path that surfaces in KANNs.py: a cell
defines a class (e.g. ``KAN``), another cell creates an instance
(``model = KAN(...)``), and the cache must restore the instance even
after ``sys.modules['__main__']`` no longer holds the class. The fix
is two cooperating pieces: ``ClassStub`` materializes the class source
into ``glbls`` before pickle blobs deserialize, and
``CellNamespaceUnpickler`` resolves ``__main__.<name>`` against the
same ``glbls`` when ``sys.modules`` doesn't have it.
"""

from __future__ import annotations

import sys
import tempfile
from typing import TYPE_CHECKING, Any

import pytest

from marimo._save.cache import MARIMO_CACHE_VERSION, Cache
from marimo._save.hash import HashKey
from marimo._save.loaders import LazyLoader
from marimo._save.stores.file import FileStore
from marimo._save.stubs import ClassStub

if TYPE_CHECKING:
    from pathlib import Path

_MISSING = object()


def _make_cell_class(qualname: str = "KAN") -> type:
    """Build a class the same way marimo's kernel does: exec into a
    glbls with ``__name__='__main__'`` and a synthetic filename whose
    contents live in ``linecache``. The class then has
    ``__module__='__main__'`` and ``inspect.getsource`` works via
    linecache — exactly mirroring a cell-defined class."""
    src = (
        f"class {qualname}:\n"
        "    def __init__(self, v: int = 0) -> None:\n"
        "        self.v = v\n"
        "    def doubled(self) -> int:\n"
        "        return self.v * 2\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src)
        tmp_path = f.name
    import linecache

    linecache.cache[tmp_path] = (
        len(src),
        None,
        [line + "\n" for line in src.splitlines()],
        tmp_path,
    )
    cell_glbls: dict[str, Any] = {
        "__name__": "__main__",
        "__file__": tmp_path,
    }
    exec(compile(src, tmp_path, "exec"), cell_glbls)
    return cell_glbls[qualname]


def _inject_into_main(cls: type) -> object:
    """Temporarily place *cls* into ``sys.modules['__main__']`` so
    pickle.dumps' reachability check passes. Returns the prior binding
    (or _MISSING) for restoration."""
    name = cls.__name__
    prior = getattr(sys.modules["__main__"], name, _MISSING)
    setattr(sys.modules["__main__"], name, cls)
    return prior


def _restore_main(cls: type, prior: object) -> None:
    name = cls.__name__
    if prior is _MISSING:
        try:
            delattr(sys.modules["__main__"], name)
        except AttributeError:
            pass
    else:
        setattr(sys.modules["__main__"], name, prior)


@pytest.fixture
def tmp_store(tmp_path: Path) -> FileStore:
    return FileStore(save_path=str(tmp_path))


class TestLazyClassRoundTrip:
    """End-to-end tests: save a Cache containing a cell-defined class
    and an instance; restore in a vacuum (no __main__ symbols)."""

    def test_save_restore_cell_defined_class_and_instance(
        self, tmp_store: FileStore
    ) -> None:
        """The canonical KANNs.py shape: producer cell saves
        {KAN: <class>, model: KAN(7)}. Restore in a fresh kernel where
        sys.modules['__main__'] does not have KAN must succeed."""
        KAN = _make_cell_class("KAN")
        prior = _inject_into_main(KAN)
        try:
            loader = LazyLoader("test", store=tmp_store)
            instance = KAN(7)
            cache = Cache(
                defs={"KAN": ClassStub(KAN), "model": instance},
                hash="round_trip_hash",
                cache_type="Pure",
                stateful_refs=set(),
                hit=False,
                meta={"version": MARIMO_CACHE_VERSION},
            )
            assert loader.save_cache(cache)
            loader.flush()
        finally:
            _restore_main(KAN, prior)

        # Simulate a fresh kernel: KAN not in sys.modules['__main__'].
        assert not hasattr(sys.modules["__main__"], "KAN")

        # Pass glbls so the loader can materialize ClassStub and use
        # the custom Unpickler for pickle blobs.
        glbls: dict[str, Any] = {"__name__": "__main__"}
        loader2 = LazyLoader("test", store=tmp_store)
        loaded = loader2.load_cache(
            HashKey("round_trip_hash", "Pure"), glbls=glbls
        )
        assert loaded is not None
        # KAN materialized into glbls.
        assert "KAN" in glbls
        # model deserialized correctly using the materialized class.
        assert loaded.defs["model"].__class__.__name__ == "KAN"
        assert loaded.defs["model"].v == 7
        assert loaded.defs["model"].doubled() == 14

    def test_restore_with_class_already_in_glbls(
        self, tmp_store: FileStore
    ) -> None:
        """When the producer cell already ran in this kernel (KAN is in
        glbls), the consumer cell's cache restores the instance using
        the existing class — no ClassStub needed in the consumer's
        manifest."""
        KAN = _make_cell_class("KAN2")
        prior = _inject_into_main(KAN)
        try:
            loader = LazyLoader("test_consumer", store=tmp_store)
            cache = Cache(
                defs={"model": KAN(11)},
                hash="consumer_hash",
                cache_type="Pure",
                stateful_refs=set(),
                hit=False,
                meta={"version": MARIMO_CACHE_VERSION},
            )
            assert loader.save_cache(cache)
            loader.flush()
        finally:
            _restore_main(KAN, prior)

        # Simulate kernel where producer cell already ran (KAN alive
        # in glbls) but __main__ does not have it.
        assert not hasattr(sys.modules["__main__"], "KAN2")
        glbls: dict[str, Any] = {"__name__": "__main__", "KAN2": KAN}
        loader2 = LazyLoader("test_consumer", store=tmp_store)
        loaded = loader2.load_cache(
            HashKey("consumer_hash", "Pure"), glbls=glbls
        )
        assert loaded is not None
        assert isinstance(loaded.defs["model"], KAN)
        assert loaded.defs["model"].v == 11

    def test_restore_without_glbls_still_works_for_non_main(
        self, tmp_store: FileStore
    ) -> None:
        """Backwards compatibility: callers that don't pass glbls still
        get the existing behavior. Non-__main__ values round-trip
        unchanged."""
        from pathlib import Path as _Path

        loader = LazyLoader("test_nomain", store=tmp_store)
        cache = Cache(
            defs={"x": 42, "p": _Path("/tmp/whatever")},
            hash="nomain_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        assert loader.save_cache(cache)
        loader.flush()

        loader2 = LazyLoader("test_nomain", store=tmp_store)
        # Call without glbls — should behave like before.
        loaded = loader2.load_cache(HashKey("nomain_hash", "Pure"))
        assert loaded is not None
        assert loaded.defs["x"] == 42
        assert loaded.defs["p"] == _Path("/tmp/whatever")

    def test_restore_missing_class_definition_fails_clearly(
        self, tmp_store: FileStore
    ) -> None:
        """If the manifest references a __main__ class but no ClassStub
        and the consumer's glbls doesn't have it either, the restore
        should fail (load returns None or raises) rather than silently
        returning a corrupt cache."""
        KAN = _make_cell_class("KAN3")
        prior = _inject_into_main(KAN)
        try:
            # Save only the instance, no ClassStub. Caller's glbls is empty.
            loader = LazyLoader("test_orphan", store=tmp_store)
            cache = Cache(
                defs={"model": KAN(1)},
                hash="orphan_hash",
                cache_type="Pure",
                stateful_refs=set(),
                hit=False,
                meta={"version": MARIMO_CACHE_VERSION},
            )
            assert loader.save_cache(cache)
            loader.flush()
        finally:
            _restore_main(KAN, prior)

        # Fresh-kernel scenario: KAN3 not in __main__ AND not in glbls.
        assert not hasattr(sys.modules["__main__"], "KAN3")
        loader2 = LazyLoader("test_orphan", store=tmp_store)
        # load_cache catches restore errors and returns None
        # (see LazyLoader.load_cache exception handler).
        loaded = loader2.load_cache(
            HashKey("orphan_hash", "Pure"), glbls={"__name__": "__main__"}
        )
        # Either None (clean failure) or no model in defs — both are
        # acceptable. What's NOT acceptable: a corrupt model object.
        assert (
            loaded is None
            or "model" not in loaded.defs
            or (loaded.defs["model"] is None)
        )
