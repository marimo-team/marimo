from __future__ import annotations

from typing import cast

import pytest

from marimo._output import utils


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


def test_uri_decode_component() -> None:
    assert utils.uri_decode_component("hello%20world") == "hello world"
    assert utils.uri_decode_component("!@#$%^&*()") == "!@#$%^&*()"
    assert utils.uri_decode_component("~.!'()") == "~.!'()"


def test_uri_encode_decode_component_not_lossy() -> None:
    test_cases = [
        "hello world",
        "!@#$%^&*()",
        "~.!'()",
        "hello%20world",
        "https://example.com/path?query=value&other=123",
        "email+address@example.com",
        "unicode_symbols_✨🌟⭐",
        "spaces    and   tabs\t\t",
        r"backslashes\and/slashes/",
        'quotes\'and"double"quotes',
        "<>[]{}|",
        "control\n\r\tcharacters",
        "math±∞≠≈∫",
        "currency¢£¥€$",
        "accents éèêë àâäã ñ",
        "chinese 你好 japanese こんにちは",
        "emojis 👋🌍🎉🎨🚀",
        "mixed_case_TEST_123",
    ]

    for item in test_cases:
        assert (
            utils.uri_decode_component(utils.uri_encode_component(item))
            == item
        )


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
