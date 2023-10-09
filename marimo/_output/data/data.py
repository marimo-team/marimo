# Copyright 2023 Marimo. All rights reserved.
import io
from typing import Union

from marimo._plugins.core.media import (
    is_data_empty,
)
from marimo._runtime.context import get_context
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
    get_context().cell_lifecycle_registry.add(item)
    return item.virtual_file


def image(data: bytes, ext: str = "png") -> VirtualFile:
    """Create a virtual file from an image.

    **Args.**

    - data: Image data in bytes

    **Returns.**

    A `VirtualFile` object.
    """
    item = VirtualFileLifecycleItem(ext=ext, buffer=data)
    get_context().cell_lifecycle_registry.add(item)
    return item.virtual_file


def any(data: Union[str, bytes, io.BytesIO], ext: str) -> VirtualFile:
    """Create a virtual file from any data.
    It can be a string, bytes, or a file-like object.
    For external URLs, these are passed through as-is.

    **Args.**

    - data: Data in bytes
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
        buffer = data.split(",")[1]
        item = VirtualFileLifecycleItem(ext=ext, buffer=buffer)
        get_context().cell_lifecycle_registry.add(item)
        return item.virtual_file

    # URL
    if isinstance(data, str):
        return VirtualFile(url=data, filename=data, buffer=b"")

    # Local file
    if isinstance(data, io.FileIO) or isinstance(data, io.BytesIO):
        # clone before reading, so we don't consume the stream
        buffer = io.BytesIO(data.getvalue()).read()
        item = VirtualFileLifecycleItem(ext=ext, buffer=buffer)
        get_context().cell_lifecycle_registry.add(item)
        return item.virtual_file

    raise ValueError(f"Unsupported data type: {type(data)}")
