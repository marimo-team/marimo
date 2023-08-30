# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._plugins import ui


def test_number_init() -> None:
    number = ui.number(1, 10)
    assert number.start == 1
    assert number.stop == 10
    assert number.step is None
    assert number.value == 1

    number = ui.number(1, 10, value=5)
    assert number.start == 1
    assert number.stop == 10
    assert number.step is None
    assert number.value == 5
    number._update(6)
    assert number.value == 6
    number._update(6.5)
    # unlike slider, number should not round because users can type
    # arbitrary numbers
    assert number.value == 6.5


def test_number_out_of_bounds() -> None:
    with pytest.raises(ValueError) as e:
        ui.number(1, 10, value=11)

    assert "out of bounds" in str(e.value)

    with pytest.raises(ValueError) as e:
        ui.number(1, 10, value=0)

    assert "out of bounds" in str(e.value)


def test_number_invalid_bounds() -> None:
    with pytest.raises(ValueError) as e:
        ui.number(1, 0)

    assert "Invalid bounds" in str(e.value)


def test_slider_init() -> None:
    slider = ui.slider(1, 10)
    assert slider.start == 1
    assert slider.stop == 10
    assert slider.step is None
    assert slider.value == 1

    slider = ui.slider(1, 10, value=5)
    assert slider.start == 1
    assert slider.stop == 10
    assert slider.step is None
    assert slider.value == 5 and isinstance(slider.value, int)

    slider = ui.slider(1, 10, value=5.0)
    assert slider.value == 5.0 and isinstance(slider.value, float)

    slider._update(6)
    assert slider.value == 6.0 and isinstance(slider.value, float)


def test_slider_invalid_bounds() -> None:
    with pytest.raises(ValueError) as e:
        ui.slider(1, 0)

    assert "Invalid bounds" in str(e.value)


def test_slider_out_of_bounds() -> None:
    with pytest.raises(ValueError) as e:
        ui.slider(1, 10, value=11)

    assert "out of bounds" in str(e.value)

    with pytest.raises(ValueError) as e:
        ui.slider(1, 10, value=0)

    assert "out of bounds" in str(e.value)


def test_text() -> None:
    assert ui.text().value == ""
    assert ui.text(value="hello world").value == "hello world"

    text = ui.text()
    text._update("value")
    assert text.value == "value"


def test_checkbox_init() -> None:
    assert not ui.checkbox().value
    assert ui.checkbox(value=True).value


def test_radio() -> None:
    radio = ui.radio(options=["1", "2", "3"], value="1")
    assert radio.value == "1"

    radio._update("2")
    assert radio.value == "2"

    radio = ui.radio(options={"1": 1, "2": 2, "3": 3}, value="1")
    assert radio.value == 1

    radio._update("2")
    assert radio.value == 2


def test_dropdown() -> None:
    dd = ui.dropdown(options=["1", "2", "3"])
    assert dd.value is None

    dd._update(["2"])
    assert dd.value == "2"

    dd = ui.dropdown(options={"1": 1, "2": 2, "3": 3}, value="1")
    assert dd.value == 1

    dd._update(["2"])
    assert dd.value == 2


def test_button() -> None:
    assert ui.button().value is None
    assert ui.button(value=1).value == 1

    # default callback does nothing
    button = ui.button(value=1)
    button._update(None)
    assert button.value == 1

    button = ui.button(on_click=lambda v: v + 1, value=0)
    assert button.value == 0
    button._update(None)
    assert button.value == 1
    button._update(None)
    assert button.value == 2


def test_on_change() -> None:
    state = []
    button = ui.checkbox(on_change=lambda v: state.append(v))
    assert not state
    button._update(False)
    assert state == [False]
    button._update(True)
    assert state == [False, True]


# TODO(akshayka): test file
# TODO(akshayka): test date
