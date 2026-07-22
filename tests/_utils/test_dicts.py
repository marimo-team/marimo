# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._utils.dicts import remove_none_values


def test_remove_none_values_drops_nones() -> None:
    assert remove_none_values({"a": 1, "b": None, "c": "x"}) == {
        "a": 1,
        "c": "x",
    }


def test_remove_none_values_keeps_falsey_non_none() -> None:
    assert remove_none_values({"z": 0, "f": False, "s": "", "n": None}) == {
        "z": 0,
        "f": False,
        "s": "",
    }


def test_remove_none_values_empty() -> None:
    assert remove_none_values({}) == {}


def test_remove_none_values_does_not_mutate_input() -> None:
    original = {"a": None, "b": 2}
    result = remove_none_values(original)
    assert result == {"b": 2}
    assert original == {"a": None, "b": 2}
