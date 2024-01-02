# Copyright 2023 Marimo. All rights reserved.
import io

from marimo._plugins.core.media import (
    guess_mime_type,
    io_to_data_url,
    is_data_empty,
)


def test_guess_mime_type() -> None:
    assert guess_mime_type(None) is None
    assert (
        guess_mime_type("data:text/plain;base64,SGVsbG8sIFdvcmxkIQ==")
        == "text/plain"
    )
    assert guess_mime_type("example.txt") == "text/plain"
    assert guess_mime_type(io.BytesIO(b"Hello, World!")) is None


def test_io_to_data_url() -> None:
    assert io_to_data_url(None, "text/plain") is None
    assert (
        io_to_data_url(io.BytesIO(b"Hello, World!"), "text/plain")
        == "data:text/plain;base64,SGVsbG8sIFdvcmxkIQ=="
    )
    assert (
        io_to_data_url(b"Hello, World!", "text/plain")
        == "data:text/plain;base64,SGVsbG8sIFdvcmxkIQ=="
    )
    assert io_to_data_url("Hello, World!", "text/plain") == "Hello, World!"


def test_is_data_empty() -> None:
    assert is_data_empty("") is True
    assert is_data_empty(b"") is True
    assert is_data_empty(io.BytesIO(b"")) is True
    assert is_data_empty("Hello, World!") is False
    assert is_data_empty(b"Hello, World!") is False
    assert is_data_empty(io.BytesIO(b"Hello, World!")) is False
