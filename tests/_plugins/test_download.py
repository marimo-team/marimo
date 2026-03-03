from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

from marimo._plugins.stateless.download import download
from marimo._runtime.functions import EmptyArgs

if TYPE_CHECKING:
    from pathlib import Path


def test_download_string():
    """Test downloading string data."""
    result = download("test data")
    args = result._component_args
    assert args["filename"] is None
    assert not args["disabled"]
    assert not args["lazy"]
    assert result._args.label == "Download"


def test_download_bytes():
    """Test downloading bytes data."""
    result = download(b"test data", filename="test.txt")
    args = result._component_args
    assert args["filename"] == "test.txt"
    assert not args["disabled"]
    assert not args["lazy"]


def test_download_bytesio():
    """Test downloading BytesIO data."""
    data = io.BytesIO(b"test data")
    result = download(data)
    args = result._component_args
    assert not args["disabled"]
    assert not args["lazy"]
    data.close()


def test_download_file(tmp_path: Path):
    """Test downloading file data."""
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(b"test data")
    with open(file_path, "rb") as f:
        result = download(f)
        args = result._component_args
    assert args["filename"] == str(file_path)
    assert not args["disabled"]
    assert not args["lazy"]


def test_download_empty():
    """Test downloading empty data."""
    result = download(b"")
    args = result._component_args
    assert args["disabled"]
    assert not args["lazy"]


async def test_download_lazy_sync():
    """Test lazy downloading with sync function."""

    def get_data():
        return b"test data"

    result = download(get_data)
    args = result._component_args
    assert args["lazy"]
    assert not args["disabled"]

    # Load the data
    loaded_data = await result._load(EmptyArgs())
    assert loaded_data.data.startswith("data:text/plain;base64")
    assert loaded_data.filename is None


async def test_download_lazy_async():
    """Test lazy downloading with async function."""

    async def get_data():
        return b"test data"

    result = download(get_data)
    args = result._component_args
    assert args["lazy"]
    assert not args["disabled"]

    # Load the data
    loaded_data = await result._load(EmptyArgs())
    assert loaded_data.data.startswith("data:text/plain;base64")
    assert loaded_data.filename is None


async def test_download_async_with_error():
    """Test async function without lazy flag raises error."""

    async def get_data():
        raise ValueError("test error")

    result = download(get_data)
    with pytest.raises(ValueError, match="test error"):
        await result._load(EmptyArgs())


def test_download_custom_label():
    """Test custom button label."""
    result = download(b"test", label="Custom Label")
    args = result._component_args
    assert result._args.label == "Custom Label"
    assert not args["lazy"]


def test_download_mimetype():
    """Test custom mimetype."""
    result = download(b"test", mimetype="text/csv")
    args = result._component_args
    assert args["data"].startswith("data:text/csv;base64")


def test_download_disabled():
    """Test disabled download button."""
    result = download(b"test", disabled=True)
    args = result._component_args
    assert args["disabled"] is True
    assert not args["lazy"]


def test_download_xlsx_bytesio():
    """Test downloading xlsx file from BytesIO with explicit filename."""
    # Create a BytesIO object with sample data (doesn't need to be valid Excel)
    data = io.BytesIO(b"fake excel data")
    result = download(
        data=data,
        filename="out.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    args = result._component_args
    # Verify filename is set correctly
    assert args["filename"] == "out.xlsx"
    assert not args["disabled"]
    assert not args["lazy"]
    # Verify the data URL uses the xlsx mimetype (not zip)
    assert args["data"].startswith(
        "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64"
    )
    data.close()


def test_download_xlsx_infer_mimetype_from_filename():
    """Test that xlsx mimetype is inferred from .xlsx filename."""
    # When mimetype is not provided, it should be inferred from filename
    data = io.BytesIO(b"fake excel data")
    result = download(
        data=data,
        filename="out.xlsx",
        # No mimetype provided - should infer from filename
    )
    args = result._component_args
    # Verify filename is set correctly
    assert args["filename"] == "out.xlsx"
    # Verify the data URL uses the xlsx mimetype (inferred from filename)
    assert args["data"].startswith(
        "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64"
    )
    data.close()


async def test_download_xlsx_lazy_with_filename():
    """Test lazy xlsx download with explicit filename."""

    def get_xlsx_data():
        return io.BytesIO(b"fake excel data")

    result = download(
        data=get_xlsx_data,
        filename="output.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    args = result._component_args
    assert args["lazy"]
    assert args["filename"] == "output.xlsx"

    # Load the data
    loaded_data = await result._load(EmptyArgs())
    assert loaded_data.data.startswith(
        "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64"
    )
    # Verify filename is preserved in lazy load response
    assert loaded_data.filename == "output.xlsx"
