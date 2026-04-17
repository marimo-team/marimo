# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from enum import Enum

import pytest

from marimo._code_mode._better_inspect import (
    _HelpableEnumMeta,
    better_dir,
    better_help,
    helpable,
)

# -- shared fixture class ---------------------------------------------------


@helpable
class _Demo:
    """A demo widget."""

    x: int

    def __init__(self, x: int = 1, hidden: str = "secret"):
        self.x = x
        self._hidden = hidden

    def greet(self, name: str = "world") -> str:
        """Say hello."""
        return f"hi {name}"

    def _private(self) -> None: ...


@pytest.fixture
def demo() -> _Demo:
    return _Demo(x=42)


# -- better_dir --------------------------------------------------------------


class TestBetterDir:
    def test_excludes_private_and_dunder(self, demo: _Demo) -> None:
        entries = better_dir(demo)
        for e in entries:
            assert not e.startswith("_")

    def test_data_attr_shows_type(self, demo: _Demo) -> None:
        assert "x: int" in better_dir(demo)

    def test_callable_shows_signature(self, demo: _Demo) -> None:
        [match] = [e for e in better_dir(demo) if e.startswith("greet")]
        assert "name" in match
        assert "str" in match
        assert "-> " in match

    def test_returns_list_of_str(self, demo: _Demo) -> None:
        result = better_dir(demo)
        assert isinstance(result, list)
        assert all(isinstance(e, str) for e in result)

    def test_sorted(self, demo: _Demo) -> None:
        result = better_dir(demo)
        assert result == sorted(result)


# -- better_help --------------------------------------------------------------


class TestBetterHelp:
    def test_header_and_docstring(self, demo: _Demo) -> None:
        out = better_help(demo)
        assert out.startswith("# _Demo\n")

    def test_attributes_section(self, demo: _Demo) -> None:
        out = better_help(demo)
        assert "Attributes:" in out
        assert "x: int" in out

    def test_methods_section(self, demo: _Demo) -> None:
        out = better_help(demo)
        assert "Methods:" in out
        assert "greet(" in out
        assert "Say hello." in out

    def test_no_private(self, demo: _Demo) -> None:
        out = better_help(demo)
        assert "_private" not in out
        assert "_hidden" not in out

    def test_returns_str(self, demo: _Demo) -> None:
        assert isinstance(better_help(demo), str)


# -- @helpable decorator ------------------------------------------------------


class TestHelpable:
    def test_rewrites_doc(self) -> None:
        assert _Demo.__doc__ is not None
        assert _Demo.__doc__.startswith("# _Demo")

    def test_preserves_original_doc(self) -> None:
        assert _Demo._original_doc__ == "A demo widget."  # type: ignore[attr-defined]

    def test_dir_uses_better_dir(self, demo: _Demo) -> None:
        assert dir(demo) == better_dir(demo)

    def test_class_still_works(self, demo: _Demo) -> None:
        assert demo.greet() == "hi world"
        assert demo.x == 42

    def test_dir_on_class_uses_better_dir(self) -> None:
        # dir(ClassName) should also use better_dir (via metaclass)
        result = dir(_Demo)
        assert all(isinstance(e, str) for e in result)
        assert not any(e.startswith("_") for e in result)
        assert any("greet" in e for e in result)

    def test_works_on_empty_class(self) -> None:
        @helpable
        class Empty:
            pass

        assert "# Empty" in (Empty.__doc__ or "")
        assert dir(Empty()) == better_dir(Empty())
        assert dir(Empty) == better_dir(Empty)


# -- enum support --------------------------------------------------------------


@helpable
class _Color(str, Enum, metaclass=_HelpableEnumMeta):
    """Primary colors."""

    red = "red"
    green = "green"
    blue = "blue"


class TestHelpableEnum:
    def test_dir_shows_only_members(self) -> None:
        result = dir(_Color)
        assert sorted(result) == [
            "blue = 'blue'",
            "green = 'green'",
            "red = 'red'",
        ]

    def test_dir_excludes_str_methods(self) -> None:
        result = dir(_Color)
        assert not any("capitalize" in e for e in result)
        assert not any("upper" in e for e in result)

    def test_help_shows_values_section(self) -> None:
        assert _Color.__doc__ is not None
        assert "# _Color" in _Color.__doc__
        assert "Values:" in _Color.__doc__
        assert "red = 'red'" in _Color.__doc__

    def test_string_equality_preserved(self) -> None:
        assert _Color.red == "red"
        assert isinstance(_Color.red, str)
