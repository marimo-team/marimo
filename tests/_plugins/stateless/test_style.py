# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import gc

from marimo import ui
from marimo._output.hypertext import Html
from marimo._plugins.stateless.style import style
from marimo._runtime.context import get_context
from marimo._runtime.runtime import Kernel


def test_style_with_dict():
    result = style("Test content", style={"color": "red", "font-size": "16px"})
    assert isinstance(result, Html)
    assert (
        result.text
        == "<div style='color:red;font-size:16px'>Test content</div>"
    )


def test_style_with_kwargs():
    result = style("Test content", color="blue", font_weight="bold")
    assert isinstance(result, Html)
    assert (
        result.text
        == "<div style='color:blue;font-weight:bold'>Test content</div>"
    )


def test_style_with_dict_and_kwargs():
    result = style("Test content", style={"color": "green"}, font_size="20px")
    assert isinstance(result, Html)
    assert (
        result.text
        == "<div style='color:green;font-size:20px'>Test content</div>"
    )


def test_style_with_snake_case_conversion():
    result = style("Test content", background_color="#f0f0f0")
    assert isinstance(result, Html)
    assert (
        result.text
        == "<div style='background-color:#f0f0f0'>Test content</div>"
    )


def test_style_with_empty_input():
    result = style("")
    assert isinstance(result, Html)
    assert result.text == "<div></div>"


def test_style_with_non_string_input():
    result = style(123)
    assert isinstance(result, Html)
    assert result.text == "<div>123</div>"


def test_style_overwrite_dict_with_kwargs():
    result = style("Test content", style={"color": "red"}, color="blue")
    assert isinstance(result, Html)
    assert result.text == "<div style='color:blue'>Test content</div>"


def test_style_keeps_ui_element_registered(executing_kernel: Kernel) -> None:
    # Regression test: a UI element wrapped with .style() (e.g. returned
    # from a helper) must stay alive and registered, otherwise its weak
    # registry entry is reaped and the element loses interactivity.
    del executing_kernel

    registry = get_context().ui_element_registry
    slider = ui.slider(1, 10)
    object_id = slider._id
    assert registry.get_object(object_id) is slider

    styled = slider.style(border="1px solid red")
    assert styled.text  # touch output

    # Drop the only direct handle; the styled wrapper must keep it alive.
    del slider
    gc.collect()

    assert object_id in registry._objects, (
        ".style() let the UI element be garbage collected; "
        "it was removed from the registry and is no longer interactive"
    )
    assert registry._objects[object_id]() is not None
