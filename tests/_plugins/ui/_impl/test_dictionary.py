# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import pytest

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


def test_update_on_frontend_value_change_only() -> None:
    d = ui.dictionary({"0": ui.button(value=0, on_click=lambda v: v + 1)})
    # Multiple updates with the same value -- should only register once
    d._update({"0": 2})
    d._update({"0": 2})
    d._update({"0": 2})
    assert d.value == {"0": 1}


def test_container_emulation() -> None:
    d = ui.dictionary({"0": ui.slider(1, 10), "1": ui.text()})
    # len
    assert len(d) == 2
    # reversed
    assert list(reversed(d)) == list(reversed(d.elements))
    # getitem
    assert d["0"] == d.elements["0"]
    assert d["1"] == d.elements["1"]
    # iter
    for a, b in zip(d, d.elements):
        assert a == b
    # contains
    assert "0" in d
    assert "1" in d
    # get
    assert d.get("0") == d["0"]
    assert d.get("0", 123) == d["0"]
    assert d.get("2") is None
    # items
    assert list(d.items()) == list(d.elements.items())
    # value
    assert list(d.values()) == list(d.elements.values())

    with pytest.raises(TypeError) as e:
        d["0"] = 1
    assert "does not support item assignment" in str(e)

    with pytest.raises(KeyError) as e:
        d["2"]
