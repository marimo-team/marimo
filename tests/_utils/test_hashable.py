# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._utils.hashable import is_hashable


def test_all_hashable_values() -> None:
    assert is_hashable(1, "a", (2, 3), None, 3.5)


def test_single_unhashable_value() -> None:
    assert not is_hashable([1, 2, 3])
    assert not is_hashable({"a": 1})
    assert not is_hashable({1, 2})


def test_mix_of_hashable_and_unhashable() -> None:
    # A single unhashable value makes the whole call unhashable.
    assert not is_hashable(1, "ok", [2])


def test_no_arguments_is_hashable() -> None:
    # hash(()) succeeds, so an empty call is considered hashable.
    assert is_hashable()


def test_tuple_nesting_an_unhashable_value() -> None:
    # Tuples are only hashable if all their contents are.
    assert not is_hashable((1, [2]))
    assert is_hashable((1, (2, 3)))
