# Copyright 2023 Marimo. All rights reserved.
from marimo._messaging.ops import VariableValue
from marimo._output.hypertext import Html
from marimo._plugins.ui._impl.input import slider


def test_value_ui_element() -> None:
    variable_value = VariableValue(name="s", value=slider(1, 10, value=5))
    assert variable_value.datatype == "slider"
    assert variable_value.value == "5"


def test_value_html() -> None:
    h = Html("<span></span>")
    variable_value = VariableValue(name="h", value=h)
    assert variable_value.datatype == "Html"
    assert variable_value.value == h.text
