# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._plugins import ui


def test_array() -> None:
    def func() -> None:
        pass

    # dropdown defaults to an unserializable value (func)
    a = ui.dropdown(options={"1": func, "2": 2}, value="1")
    b = ui.text(value="hello")
    c = ui.slider(1, 10, value=2)

    array = ui.array([a, b, c])
    assert array.value == [func, "hello", 2]

    # make sure elements are cloned
    assert array.elements[0].text != a.text
    assert array.elements[1].text != b.text
    assert array.elements[2].text != c.text

    assert array.elements[0]._id != a._id
    assert array.elements[1]._id != b._id
    assert array.elements[2]._id != c._id

    array._update({"0": "2"})
    array._update({"1": "goodbye", "2": 1})
    assert array.value == [2, "goodbye", 1]


def test_nested_array() -> None:
    inner = ui.array([ui.slider(1, 10), ui.text()])
    outer = ui.array([inner, ui.text()])

    # make sure elements are cloned
    assert outer.elements[0].text != inner.text
    assert outer.elements[0]._inner_text != inner._inner_text

    # updating outer's inner array should not update original inner array
    outer._update({"0": {"0": 7}})
    outer._update({"0": {"1": "hello"}})
    assert outer.value == [[7, "hello"], ""]
    assert inner.value == [1, ""]


def test_update_on_frontend_value_change_only() -> None:
    array = ui.array([ui.button(value=0, on_click=lambda v: v + 1)])
    # Multiple updates with the same value -- should only register once
    array._update({"0": 2})
    array._update({"0": 2})
    array._update({"0": 2})
    assert array.value == [1]


def test_update_checks_against_frontend_value() -> None:
    class NoEquality:
        def __init__(self) -> None:
            pass

        def __eq__(self, other: object) -> bool:
            del other
            raise ValueError

        def __neq__(self, other: object) -> bool:
            del other
            raise ValueError

    v = NoEquality()
    array = ui.array([ui.dropdown({"option": v})])
    # smoke test: don't check against backend value, which will raise
    array._update({"0": ["option"]})
    assert len(array.value) == 1
    assert isinstance(array.value[0], NoEquality)


def test_container_emulation() -> None:
    array = ui.array([ui.slider(1, 10), ui.text()])
    # len
    assert len(array) == 2
    # reversed
    assert list(reversed(array)) == list(reversed(array.elements))
    # getitem
    assert array[0] == array.elements[0]
    assert array[1] == array.elements[1]
    # iter
    for a, b in zip(array, array.elements):
        assert a == b
    # contains
    assert array[0] in array
    assert array[1] in array

    with pytest.raises(TypeError) as e:
        array[0] = 1
    assert "does not support item assignment" in str(e)
