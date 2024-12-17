from __future__ import annotations

import base64
from typing import cast

import pytest

from marimo._output import utils


def test_build_data_url() -> None:
    data = base64.b64encode(b"test")
    url = utils.build_data_url("text/plain", data)
    assert url == "data:text/plain;base64,dGVzdA=="


def test_flatten_string() -> None:
    text = """
    hello
    world
    """
    assert utils.flatten_string(text) == "helloworld"


def test_create_style() -> None:
    # Empty dict returns None
    assert utils.create_style({}) is None

    # Basic key-value pairs
    style = utils.create_style({"color": "red", "width": "100px"})
    assert style == "color: red;width: 100px"

    # None values are filtered out
    style = utils.create_style({"color": "red", "width": None})
    assert style == "color: red"

    # Numeric values
    style = utils.create_style({"width": 100, "height": 50.5})
    assert style == "width: 100;height: 50.5"


def test_uri_encode_component() -> None:
    # Test basic string
    assert utils.uri_encode_component("hello world") == "hello%20world"

    # Test special characters
    assert utils.uri_encode_component("!@#$%^&*()") == "!%40%23%24%25%5E%26*()"

    # Test safe characters
    assert utils.uri_encode_component("~.!'()") == "~.!'()"


def test_normalize_dimension() -> None:
    # Test None
    assert utils.normalize_dimension(None) is None

    # Test integers
    assert utils.normalize_dimension(100) == "100px"

    # Test floats
    assert utils.normalize_dimension(50.5) == "50.5px"

    # Test strings with units
    assert utils.normalize_dimension("100%") == "100%"
    assert utils.normalize_dimension("50vh") == "50vh"

    # Test numeric strings
    assert utils.normalize_dimension("100") == "100px"

    # Test invalid input
    with pytest.raises(ValueError):
        utils.normalize_dimension(cast(str, ["invalid"]))
