# Copyright 2026 Marimo. All rights reserved.
"""Tests for ClassStub — source-based serialization of cell-defined classes."""

from __future__ import annotations

import linecache
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

import pytest

from marimo._save.stubs.class_stub import ClassStub


class TestClassStubBasics:
    @staticmethod
    def test_load_populates_glbls() -> None:
        """ClassStub.load returns the class AND leaves it in glbls
        so subsequent pickle deserialization can find it."""
        # Build a ClassStub by hand from a known dump.
        code = textwrap.dedent(
            """
            class Bar:
                value = 42
            """
        )
        stub = ClassStub.from_dump((code, "<Bar>", 1, "Bar"))
        glbls: dict[str, Any] = {"__name__": "__main__"}
        cls = stub.load(glbls)
        assert cls is not None
        assert cls.__name__ == "Bar"
        assert glbls["Bar"] is cls
        assert cls.value == 42

    @staticmethod
    def test_load_synthetic_filename_populates_linecache() -> None:
        """When the filename starts with '<', linecache is seeded so the
        class is debuggable post-load (tracebacks render the source)."""
        code = textwrap.dedent(
            """
            class Baz:
                def hello(self) -> str:
                    return "hi"
            """
        )
        synth_name = "<Baz_test>"
        # Clear any prior entry.
        linecache.cache.pop(synth_name, None)
        stub = ClassStub.from_dump((code, synth_name, 1, "Baz"))
        glbls: dict[str, Any] = {"__name__": "__main__"}
        stub.load(glbls)
        assert synth_name in linecache.cache
        # And the class works.
        assert glbls["Baz"]().hello() == "hi"

    @staticmethod
    def test_load_real_filename_does_not_touch_linecache() -> None:
        """When the filename is a real path (no '<' prefix), we trust
        Python's normal linecache lookup and do not overwrite it."""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            src = "class Qux:\n    x = 1\n"
            f.write(src)
            tmp_path = f.name
        try:
            stub = ClassStub.from_dump((src, tmp_path, 1, "Qux"))
            # Pre-seed linecache with a sentinel to verify we DON'T overwrite.
            linecache.cache[tmp_path] = (
                999,
                None,
                ["SENTINEL\n"],
                tmp_path,
            )
            glbls: dict[str, Any] = {"__name__": "__main__"}
            stub.load(glbls)
            # Sentinel still there — load did not blow it away.
            assert linecache.cache[tmp_path][2] == ["SENTINEL\n"]
            assert glbls["Qux"].x == 1
        finally:
            linecache.cache.pop(tmp_path, None)
            Path(tmp_path).unlink(missing_ok=True)


class TestClassStubFromLiveClass:
    @staticmethod
    def test_from_live_class_in_temp_module() -> None:
        """End-to-end: take a live class from a temp module, ClassStub it,
        round-trip through dump/from_dump, and verify the class works."""
        src = textwrap.dedent(
            """
            class Widget:
                def __init__(self, n: int) -> None:
                    self.n = n

                def squared(self) -> int:
                    return self.n * self.n
            """
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(src)
            tmp_path = f.name
        module_name = "_test_class_stub_live"
        try:
            module = type(sys)(module_name)
            module.__file__ = tmp_path
            sys.modules[module_name] = module
            # Populate linecache so inspect.getsource works.
            linecache.cache[tmp_path] = (
                len(src),
                None,
                [line + "\n" for line in src.splitlines()],
                tmp_path,
            )
            exec(compile(src, tmp_path, "exec"), module.__dict__)
            cls = module.Widget

            stub = ClassStub(cls)
            dump = stub.dump()
            assert "class Widget" in dump[0]

            # Reload in a vacuum.
            fresh_stub = ClassStub.from_dump(dump)
            fresh_glbls: dict[str, Any] = {"__name__": "__main__"}
            fresh_stub.load(fresh_glbls)
            assert fresh_glbls["Widget"](5).squared() == 25
        finally:
            sys.modules.pop(module_name, None)
            linecache.cache.pop(tmp_path, None)
            Path(tmp_path).unlink(missing_ok=True)


class TestClassStubFailures:
    @staticmethod
    def test_unsourcable_class_raises_on_init() -> None:
        """A class with no discoverable source (e.g. built via type())
        cannot be ClassStub'd. The error must surface at construction
        time so the save path can fall back to UnhashableStub before
        writing a corrupt blob."""
        # type(...) classes have no source file inspect can find.
        DynCls = type("DynCls", (), {"x": 1})
        with pytest.raises((TypeError, OSError)):
            ClassStub(DynCls)
