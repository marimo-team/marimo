# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._plugins import ui


def test_dictionary() -> None:
    def func() -> None:
        pass

    # dropdown defaults to an unserializable value (func)
    a = ui.dropdown(options={"1": func, "2": 2}, value="1")
    b = ui.text(value="hello")
    c = ui.slider(1, 10, value=2)

    dictionary = ui.dictionary({"a": a, "b": b, "c": c})
    assert dictionary.value == {"a": func, "b": "hello", "c": 2}

    # make sure elements are cloned
    assert dictionary.elements["a"].text != a.text
    assert dictionary.elements["b"].text != b.text
    assert dictionary.elements["c"].text != c.text

    assert dictionary.elements["a"]._id != a._id
    assert dictionary.elements["b"]._id != b._id
    assert dictionary.elements["c"]._id != c._id

    dictionary._update({"a": "2"})
    dictionary._update({"b": "goodbye", "c": 1})
    assert dictionary.value == {"a": 2, "b": "goodbye", "c": 1}


def test_nested_dict() -> None:
    inner = ui.dictionary({"slider": ui.slider(1, 10)})
    outer = ui.dictionary({"inner": inner})

    # make sure elements are cloned
    assert outer.elements["inner"].text != inner.text
    assert outer.elements["inner"]._inner_text != inner._inner_text

    # updating outer's inner should not update original inner
    outer._update({"inner": {"slider": 7}})
    assert outer.value == {"inner": {"slider": 7}}
    assert inner.value == {"slider": 1}
