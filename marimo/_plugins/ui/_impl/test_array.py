# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

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
