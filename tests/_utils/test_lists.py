# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._utils.lists import as_list, first


def test_first_from_list() -> None:
    assert first([10, 20, 30]) == 10


def test_first_from_tuple() -> None:
    assert first((7,)) == 7


def test_first_non_iterable_returns_value() -> None:
    assert first(42) == 42


def test_first_empty_iterable_raises() -> None:
    raised = False
    try:
        first([])
    except StopIteration:
        raised = True
    assert raised


def test_first_string_yields_first_character() -> None:
    # str is Iterable[str]; first returns the first code unit.
    assert first("abc") == "a"


def test_as_list_none() -> None:
    assert as_list(None) == []


def test_as_list_already_list() -> None:
    value = [1, 2]
    assert as_list(value) == [1, 2]


def test_as_list_scalar() -> None:
    assert as_list("x") == ["x"]
    assert as_list(0) == [0]
