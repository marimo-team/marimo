# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.core.media import (
    guess_mime_type,
    io_to_data_url,
    is_data_empty,
)

if TYPE_CHECKING:
    import pathlib


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


@pytest.mark.skipif(
    not DependencyManager.pillow.has(), reason="pillow not installed"
)
def test_pil_image() -> None:
    from PIL import Image

    # Create a small test image in memory
    img = Image.new("RGB", (10, 10), color="red")
    res = io_to_data_url(img, "image/png")
    assert res is not None
    assert res.startswith("data:image/png;base64,")


@pytest.mark.skipif(
    not DependencyManager.numpy.has(), reason="NumPy not installed"
)
def test_numpy_array() -> None:
    import numpy as np

    res = io_to_data_url(np.array([[1, 2], [3, 4]]), "image/png")
    assert res is not None
    assert res.startswith("data:image/png;base64,")


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test_pandas_dataframe() -> None:
    import pandas as pd

    res = io_to_data_url(pd.DataFrame({"a": [1, 2]}), "text/csv")
    assert res is not None
    assert res.startswith("data:text/csv;base64,")


def test_paths_and_urls(tmp_path: pathlib.Path) -> None:
    # Paths
    test_file = tmp_path / "file.txt"
    test_file.write_text("test content")
    res = io_to_data_url(test_file, "text/plain")
    assert res is not None
    assert res.startswith("data:text/plain;base64,")

    # URLs remain unchanged
    assert (
        io_to_data_url("https://example.com/image.jpg", "image/jpeg")
        == "https://example.com/image.jpg"
    )


def test_is_data_empty() -> None:
    assert is_data_empty("") is True
    assert is_data_empty(b"") is True
    assert is_data_empty(io.BytesIO(b"")) is True
    assert is_data_empty("Hello, World!") is False
    assert is_data_empty(b"Hello, World!") is False
    assert is_data_empty(io.BytesIO(b"Hello, World!")) is False
