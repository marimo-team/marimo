# Copyright 2024 Marimo. All rights reserved.
import base64
import io
from typing import TYPE_CHECKING, Union

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.core.media import is_data_empty
from marimo._runtime.context import get_context
from marimo._runtime.virtual_file import (
    EMPTY_VIRTUAL_FILE,
    VirtualFile,
    VirtualFileLifecycleItem,
)

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl


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


def csv(
    data: Union[str, bytes, io.BytesIO, "pd.DataFrame", "pl.DataFrame"]
) -> VirtualFile:
    """Create a virtual file for CSV data.

    **Args.**

    - data: CSV data in bytes, or string representing a data URL, external URL
        or a Pandas DataFrame

    **Returns.**

    A `VirtualFile` object.
    """
    # Pandas DataFrame
    if DependencyManager.has_pandas():
        import pandas as pd

        if isinstance(data, pd.DataFrame):
            buffer = data.to_csv(
                index=False,
            ).encode("utf-8")
            return any_data(buffer, ext="csv")

    # Polars DataFrame
    if DependencyManager.has_polars():
        import polars as pl

        if isinstance(data, pl.DataFrame):
            buffer = data.write_csv().encode("utf-8")
            return any_data(buffer, ext="csv")

    return any_data(data, ext="csv")  # type: ignore


def json(
    data: Union[str, bytes, io.BytesIO, "pd.DataFrame", "pl.DataFrame"]
) -> VirtualFile:
    """Create a virtual file for JSON data.

    **Args.**

    - data: JSON data in bytes, or string representing a data URL, external URL
        or a Pandas DataFrame

    **Returns.**

    A `VirtualFile` object.
    """
    # Pandas DataFrame
    if DependencyManager.has_pandas():
        import pandas as pd

        if isinstance(data, pd.DataFrame):
            buffer = data.to_json(orient="records").encode("utf-8")
            return any_data(buffer, ext="json")

    # Polars DataFrame
    if DependencyManager.has_polars():
        import polars as pl

        if isinstance(data, pl.DataFrame):
            buffer = data.write_json(row_oriented=True).encode("utf-8")
            return any_data(buffer, ext="json")

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
        get_context().cell_lifecycle_registry.add(item)
        return item.virtual_file

    # URL
    if isinstance(data, str) and data.startswith("http"):
        return VirtualFile.from_external_url(data)

    # Bytes
    if isinstance(data, bytes):
        item = VirtualFileLifecycleItem(ext=ext, buffer=data)
        get_context().cell_lifecycle_registry.add(item)
        return item.virtual_file

    # String
    if isinstance(data, str):
        item = VirtualFileLifecycleItem(ext=ext, buffer=data.encode("utf-8"))
        get_context().cell_lifecycle_registry.add(item)
        return item.virtual_file

    # BytesIO
    if isinstance(data, io.BytesIO):
        # clone before reading, so we don't consume the stream
        buffer = io.BytesIO(data.getvalue()).read()
        item = VirtualFileLifecycleItem(ext=ext, buffer=buffer)
        get_context().cell_lifecycle_registry.add(item)
        return item.virtual_file

    raise ValueError(f"Unsupported data type: {type(data)}")
