# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest

from marimo._utils.flatten import CyclicStructureError, flatten

L = List[Any]
T = Tuple[Any, ...]
D = Dict[Any, Any]


def test_flat_list() -> None:
    x = [1, 2, 3]
    v, u = flatten(x)
    assert v == [1, 2, 3]
    assert u(v) == x
    assert u([4, 5, 6]) == [4, 5, 6]


def test_flat_tuple() -> None:
    x = (1, 2, 3)
    v, u = flatten(x)
    assert v == [1, 2, 3]
    assert u(v) == x
    assert u([4, 5, 6]) == (4, 5, 6)


def test_flat_dict() -> None:
    x = {1: 4, 2: 5, 3: 6}
    v, u = flatten(x)
    assert v == [4, 5, 6]
    assert u(v) == x
    assert u([7, 8, 9]) == {1: 7, 2: 8, 3: 9}


def test_flat_empty_list() -> None:
    x: L = []
    v, u = flatten(x)
    assert v == []
    assert u(v) == []


def test_flat_empty_tuple() -> None:
    x: T = tuple()
    v, u = flatten(x)
    assert v == []
    assert u(v) == x


def test_flat_empty_dict() -> None:
    x: D = {}
    v, u = flatten(x)
    assert v == []
    assert u(v) == x


def test_flat_singleton_list() -> None:
    x = [1]
    v, u = flatten(x)
    assert v == [1]
    assert u(v) == [1]
    assert u([2]) == [2]


def test_flat_singleton_tuple() -> None:
    x = (1,)
    v, u = flatten(x)
    assert v == [1]
    assert u(v) == x
    assert u([2]) == (2,)


def test_flat_singleton_dict() -> None:
    x = {1: 2}
    v, u = flatten(x)
    assert v == [2]
    assert u(v) == x
    assert u([3]) == {1: 3}


def test_nested_list() -> None:
    x = [0, 1, [], 2, [3, [4, 5]], [6]]
    v, u = flatten(x)
    assert v == [0, 1, 2, 3, 4, 5, 6]
    assert u(v) == x
    assert u([7, 8, 9, 10, 11, 12, 13]) == [7, 8, [], 9, [10, [11, 12]], [13]]


def test_nested_tuple() -> None:
    x: T = (0, 1, tuple(), 2, (3, (4, 5)), (6,))
    v, u = flatten(x)
    assert v == [0, 1, 2, 3, 4, 5, 6]
    assert u(v) == x
    assert u([7, 8, 9, 10, 11, 12, 13]) == (
        7,
        8,
        tuple(),
        9,
        (10, (11, 12)),
        (13,),
    )


def test_nested_dict() -> None:
    x = {
        "a": 0,
        "b": 1,
        "c": dict(),
        "d": 2,
        "e": {"f": 3, "g": {"h": 4, "i": 5}},
        "j": {"k": 6},
    }
    v, u = flatten(x)
    assert v == [0, 1, 2, 3, 4, 5, 6]
    assert u(v) == x
    assert u([7, 8, 9, 10, 11, 12, 13]) == {
        "a": 7,
        "b": 8,
        "c": dict(),
        "d": 9,
        "e": {"f": 10, "g": {"h": 11, "i": 12}},
        "j": {"k": 13},
    }


def test_nested_mix() -> None:
    x = [
        0,
        1,
        {"c": []},
        (2,),
        {"d": 3, "e": [4, 5]},
        [6, (7, 8)],
    ]
    v, u = flatten(x)
    assert v == [0, 1, 2, 3, 4, 5, 6, 7, 8]
    assert u(v) == x
    assert u([9, 10, 11, 12, 13, 14, 15, 16, 17]) == [
        9,
        10,
        {"c": []},
        (11,),
        {"d": 12, "e": [13, 14]},
        [15, (16, 17)],
    ]


def test_nested_mix_repack_objects() -> None:
    x = [
        0,
        1,
        {"c": []},
        (2,),
        {"d": 3, "e": [4, 5]},
        [6, (7, 8)],
    ]
    v, u = flatten(x)
    assert v == [0, 1, 2, 3, 4, 5, 6, 7, 8]
    assert u(v) == x
    assert u([[], [], [], [], [], [], [], {}, tuple()]) == [
        [],
        [],
        {"c": []},
        ([],),
        {"d": [], "e": [[], []]},
        [[], ({}, tuple())],
    ]


def test_flatten_cyclic_structure_raises() -> None:
    x: list[Any] = []
    x.append(x)
    # should raise since x contains itself
    with pytest.raises(CyclicStructureError):
        flatten(x)

    d: dict[Any, Any] = {}
    d["key"] = d
    # should raise since d contains itself
    with pytest.raises(CyclicStructureError):
        flatten(d)


def test_flatten_repeated_structure_does_not_raise() -> None:
    x: list[Any] = []
    y = [x, x, x]
    # should not raise
    flatten(y)
