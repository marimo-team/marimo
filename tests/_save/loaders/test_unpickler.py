# Copyright 2026 Marimo. All rights reserved.
"""Tests for CellNamespaceUnpickler — pickle.find_class fallback into glbls."""

from __future__ import annotations

import io
import pickle
import sys
from pathlib import Path
from typing import Any

import pytest

from marimo._save.loaders.unpickler import (
    CellNamespaceUnpickler,
    pickle_load_with_namespace,
)


def _make_main_class() -> type:
    """Build a class whose __module__ is '__main__'. Caller is responsible
    for injecting into sys.modules['__main__'] while pickling and stripping
    it before loading — that's the exact mismatch the unpickler fixes."""
    src = (
        "class Foo:\n"
        "    def __init__(self, v: int) -> None:\n"
        "        self.v = v\n"
        "    def doubled(self) -> int:\n"
        "        return self.v * 2\n"
    )
    glbls: dict[str, Any] = {"__name__": "__main__"}
    exec(compile(src, "<Foo>", "exec"), glbls)
    cls = glbls["Foo"]
    cls.__module__ = "__main__"
    return cls


def _dump_then_strip_main(instance: Any, cls: type) -> bytes:
    """Pickle *instance* with *cls* temporarily injected into __main__,
    then strip the injection. The resulting blob references __main__.<cls>
    but the lookup will fail without unpickler help — exactly the
    cross-session scenario."""
    name = cls.__name__
    prior = getattr(sys.modules["__main__"], name, _MISSING)
    setattr(sys.modules["__main__"], name, cls)
    try:
        blob = pickle.dumps(instance)
    finally:
        if prior is _MISSING:
            delattr(sys.modules["__main__"], name)
        else:
            setattr(sys.modules["__main__"], name, prior)
    return blob


_MISSING = object()


class TestUnpicklerMainResolution:
    @staticmethod
    def test_resolves_main_class_from_glbls() -> None:
        """Pickled instance of a cell-defined class round-trips when glbls
        holds the class — even though sys.modules['__main__'] does not."""
        Foo = _make_main_class()
        instance = Foo(7)
        blob = _dump_then_strip_main(instance, Foo)

        # Sanity: vanilla pickle.loads fails because __main__.Foo doesn't exist
        # in the real __main__ module (the dump-helper stripped it).
        with pytest.raises(AttributeError):
            pickle.loads(blob)

        # CellNamespaceUnpickler with glbls succeeds.
        glbls = {"Foo": Foo}
        result = CellNamespaceUnpickler(io.BytesIO(blob), glbls).load()
        assert isinstance(result, Foo)
        assert result.doubled() == 14

    @staticmethod
    def test_falls_through_for_real_modules() -> None:
        """For modules other than '__main__', behavior matches vanilla pickle."""
        p = Path("/tmp/whatever")
        blob = pickle.dumps(p)

        # Both vanilla and CellNamespaceUnpickler round-trip pathlib.Path.
        assert pickle.loads(blob) == p
        assert CellNamespaceUnpickler(io.BytesIO(blob), {}).load() == p

    @staticmethod
    def test_glbls_wins_over_real_main() -> None:
        """When sys.modules['__main__'] happens to have a colliding name,
        the cell namespace wins. Cell scope is the source of truth."""
        Foo = _make_main_class()
        instance = Foo(3)
        blob = _dump_then_strip_main(instance, Foo)

        class _Decoy:
            def __init__(self, *_args: object, **_kw: object) -> None:
                raise AssertionError("decoy should not be instantiated")

        sys.modules["__main__"].Foo = _Decoy  # type: ignore[attr-defined]
        try:
            glbls = {"Foo": Foo}
            result = CellNamespaceUnpickler(io.BytesIO(blob), glbls).load()
            assert isinstance(result, Foo)
        finally:
            del sys.modules["__main__"].Foo

    @staticmethod
    def test_glbls_missing_class_raises_attribute_error() -> None:
        """If glbls has no entry for the requested __main__ name, fall back
        to the default behavior (which raises AttributeError) — surfaces a
        clear error rather than silently substituting None."""
        Foo = _make_main_class()
        blob = _dump_then_strip_main(Foo(1), Foo)
        with pytest.raises(AttributeError):
            CellNamespaceUnpickler(io.BytesIO(blob), {}).load()


class TestPickleLoadWithNamespaceEntryPoint:
    @staticmethod
    def test_entry_point_signature() -> None:
        """pickle_load_with_namespace mirrors _pickle_load's call shape
        but threads glbls through. Matches BLOB_DESERIALIZERS signature
        (data, type_hint)."""
        Foo = _make_main_class()
        instance = Foo(5)
        blob = _dump_then_strip_main(instance, Foo)
        glbls = {"Foo": Foo}
        result = pickle_load_with_namespace(blob, None, glbls)
        assert isinstance(result, Foo)
        assert result.v == 5

    @staticmethod
    def test_entry_point_no_glbls_behaves_like_pickle() -> None:
        """With glbls=None, the entry point degrades to vanilla pickle.loads —
        useful for non-__main__ blobs where the unpickler buys you nothing."""
        blob = pickle.dumps({"a": 1, "b": [1, 2, 3]})
        result = pickle_load_with_namespace(blob, None, None)
        assert result == {"a": 1, "b": [1, 2, 3]}


class TestUnpicklerNestedClass:
    @staticmethod
    def test_class_instance_inside_dict() -> None:
        """Instance of a cell-defined class inside a container round-trips."""
        Foo = _make_main_class()
        container = {"x": Foo(11), "y": [Foo(22), Foo(33)]}
        blob = _dump_then_strip_main(container, Foo)
        glbls = {"Foo": Foo}
        result = pickle_load_with_namespace(blob, None, glbls)
        assert isinstance(result["x"], Foo)
        assert result["x"].v == 11
        assert all(isinstance(item, Foo) for item in result["y"])
        assert [item.v for item in result["y"]] == [22, 33]
