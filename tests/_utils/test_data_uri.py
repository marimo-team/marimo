from __future__ import annotations

import base64

import pytest

from marimo._utils.data_uri import build_data_url, from_data_uri


def test_build_data_url():
    test_data = b"Hello, World!"
    encoded = base64.b64encode(test_data)
    url = build_data_url("text/plain", encoded)
    assert url == f"data:text/plain;base64,{encoded.decode('utf-8')}"

    # Test with binary data
    binary_data = b"\x00\x01\x02\x03"
    encoded = base64.b64encode(binary_data)
    url = build_data_url("application/octet-stream", encoded)
    assert (
        url
        == f"data:application/octet-stream;base64,{encoded.decode('utf-8')}"
    )

    # Test with JSON data
    json_data = b'{"key": "value"}'
    encoded = base64.b64encode(json_data)
    url = build_data_url("application/json", encoded)
    assert url == f"data:application/json;base64,{encoded.decode('utf-8')}"


def test_build_data_url_newline_handling():
    test_data = b"Hello\nWorld"
    encoded = base64.b64encode(test_data)
    url = build_data_url("text/plain", encoded)
    assert "\n" not in url
    assert url == "data:text/plain;base64," + encoded.decode("utf-8").replace(
        "\n", ""
    )


def test_from_data_uri():
    # Test text data
    test_data = b"Hello, World!"
    encoded = base64.b64encode(test_data).decode()
    uri = f"data:text/plain;base64,{encoded}"
    mime_type, data = from_data_uri(uri)
    assert mime_type == "text/plain"
    assert data == test_data

    # Test JSON data
    json_data = b'{"key": "value"}'
    encoded = base64.b64encode(json_data).decode()
    uri = f"data:application/json;base64,{encoded}"
    mime_type, data = from_data_uri(uri)
    assert mime_type == "application/json"
    assert data == json_data

    # Test binary data
    binary_data = b"\x00\x01\x02\x03"
    encoded = base64.b64encode(binary_data).decode()
    uri = f"data:application/octet-stream;base64,{encoded}"
    mime_type, data = from_data_uri(uri)
    assert mime_type == "application/octet-stream"
    assert data == binary_data


def test_from_data_uri_invalid_input():
    with pytest.raises(AssertionError):
        from_data_uri("not-a-data-uri")

    with pytest.raises(AssertionError):
        from_data_uri(123)  # type: ignore

    # Valid prefix but invalid base64
    with pytest.raises(ValueError):
        from_data_uri("data:text/plain;base64,not-base64!")


def test_build_data_url_invalid_input():
    with pytest.raises(AssertionError):
        build_data_url(None, b"data")  # type: ignore
