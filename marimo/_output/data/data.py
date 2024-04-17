# Copyright 2024 Marimo. All rights reserved.
import base64
import io
from typing import Union

from marimo._plugins.core.media import is_data_empty
from marimo._runtime.virtual_file import (
    EMPTY_VIRTUAL_FILE,
    VirtualFile,
    VirtualFileLifecycleItem,
)


def pdf(data: bytes) -> VirtualFile:
    """Create a virtual file from a PDF.

    **Args.**

    - data: PDF data in bytes

    **Returns.**

    A `VirtualFile` object.
    """
    item = VirtualFileLifecycleItem(ext="pdf", buffer=data)
    item.add_to_cell_lifecycle_registry()
    return item.virtual_file


def image(data: bytes, ext: str = "png") -> VirtualFile:
    """Create a virtual file from an image.

    **Args.**

    - data: Image data in bytes

    **Returns.**

    A `VirtualFile` object.
    """
    item = VirtualFileLifecycleItem(ext=ext, buffer=data)
    item.add_to_cell_lifecycle_registry()
    return item.virtual_file


def audio(data: bytes, ext: str = "wav") -> VirtualFile:
    """Create a virtual file from audio.

    **Args.**

    - data: Audio data in bytes

    **Returns.**

    A `VirtualFile` object.
    """
    item = VirtualFileLifecycleItem(ext=ext, buffer=data)
    item.add_to_cell_lifecycle_registry()
    return item.virtual_file


def csv(data: Union[str, bytes, io.BytesIO]) -> VirtualFile:
    """Create a virtual file for CSV data.

    **Args.**

    - data: CSV data in bytes, or string representing a data URL, external URL
        or a Pandas DataFrame

    **Returns.**

    A `VirtualFile` object.
    """
    return any_data(data, ext="csv")  # type: ignore


def json(data: Union[str, bytes, io.BytesIO]) -> VirtualFile:
    """Create a virtual file for JSON data.

    **Args.**

    - data: JSON data in bytes, or string representing a data URL, external URL
        or a Pandas DataFrame

    **Returns.**

    A `VirtualFile` object.
    """
    return any_data(data, ext="json")  # type: ignore


def js(data: str) -> VirtualFile:
    """Create a virtual file for JavaScript data.

    **Args.**

    - data: JavaScript data as a string

    **Returns.**

    A `VirtualFile` object.
    """
    return any_data(data, ext="js")


def html(data: str) -> VirtualFile:
    """Create a virtual file for HTML data.

    **Args.**

    - data: HTML data as a string

    **Returns.**

    A `VirtualFile` object.
    """
    return any_data(data, ext="html")


def any_data(data: Union[str, bytes, io.BytesIO], ext: str) -> VirtualFile:
    """Create a virtual file from any data.

    It can be a string, bytes, or a file-like object.
    For external URLs, these are passed through as-is.

    **Args.**

    - data: Data in bytes, or string representing a data URL or external URL
    - ext: File extension

    **Returns.**

    A `VirtualFile` object.
    """
    if data is None:
        return EMPTY_VIRTUAL_FILE

    if is_data_empty(data):
        return EMPTY_VIRTUAL_FILE

    # Base64 encoded data
    if isinstance(data, str) and data.startswith("data:"):
        base64str = data.split(",")[1]
        buffer = base64.b64decode(base64str)
        item = VirtualFileLifecycleItem(ext=ext, buffer=buffer)
        item.add_to_cell_lifecycle_registry()
        return item.virtual_file

    # URL
    if isinstance(data, str) and data.startswith("http"):
        return VirtualFile.from_external_url(data)

    # Bytes
    if isinstance(data, bytes):
        item = VirtualFileLifecycleItem(ext=ext, buffer=data)
        item.add_to_cell_lifecycle_registry()
        return item.virtual_file

    # String
    if isinstance(data, str):
        item = VirtualFileLifecycleItem(ext=ext, buffer=data.encode("utf-8"))
        item.add_to_cell_lifecycle_registry()
        return item.virtual_file

    # BytesIO
    if isinstance(data, io.BytesIO):
        # clone before reading, so we don't consume the stream
        buffer = io.BytesIO(data.getvalue()).read()
        item = VirtualFileLifecycleItem(ext=ext, buffer=buffer)
        item.add_to_cell_lifecycle_registry()
        return item.virtual_file

    raise ValueError(f"Unsupported data type: {type(data)}")
