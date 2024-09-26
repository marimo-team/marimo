# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.hypertext import Html
from marimo._plugins.stateless.style import style


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
