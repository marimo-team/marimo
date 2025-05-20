# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
import io
import mimetypes
import pathlib
from typing import TYPE_CHECKING, Any, Optional, Union, cast
from urllib.parse import urlparse

import narwhals.stable.v1 as nw

from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.narwhals_utils import can_narwhalify

if TYPE_CHECKING:
    import numpy.typing as npt
    from pandas import DataFrame
    from PIL.Image import Image as PILImage


def guess_mime_type(
    src: Union[str, bytes, io.BytesIO, io.BufferedReader, None],
) -> Optional[str]:
    """Guess the MIME type of a file."""
    if src is None:
        return None

    if isinstance(src, str) and src.startswith("data:"):
        return src.split(";")[0].split(":")[1]

    if isinstance(src, str):
        return mimetypes.guess_type(src)[0]

    if isinstance(src, io.FileIO):
        return mimetypes.guess_type(src.name)[0]

    if isinstance(src, io.BufferedReader):
        return mimetypes.guess_type(src.name)[0]

    return None


def mime_type_to_ext(mime_type: str) -> Optional[str]:
    return mimetypes.guess_extension(mime_type, strict=False)


def io_to_data_url(
    src: Union[
        str,
        bytes,
        io.BytesIO,
        io.BufferedReader,
        pathlib.Path,
        PILImage,
        npt.NDArray[Any],
        DataFrame,
        None,
    ],
    fallback_mime_type: str,
) -> Optional[str]:
    """Convert various data types to a data URL.

    Supports:
    - File-like objects (BytesIO, BufferedReader)
    - Bytes
    - Strings (URLs or file paths)
    - PIL Images
    - NumPy arrays
    - Pandas DataFrames
    - Pathlib Paths
    """
    if src is None:
        return None

    # Handle existing file-like objects
    if isinstance(src, (io.BufferedIOBase, io.RawIOBase, io.BufferedReader)):
        pos = src.tell()
        base64_string = base64.b64encode(src.read()).decode("utf-8")
        src.seek(pos)
        file_type = guess_mime_type(src) or fallback_mime_type
        return f"data:{file_type};base64,{base64_string}"

    # Handle bytes directly
    if isinstance(src, bytes):
        base64_string = base64.b64encode(src).decode("utf-8")
        return f"data:{fallback_mime_type};base64,{base64_string}"

    # Handle PIL Images
    if DependencyManager.pillow.imported():
        from PIL import Image

        if Image and isinstance(src, Image.Image):
            img_byte_arr = io.BytesIO()
            src.save(img_byte_arr, format=src.format or "PNG")
            img_byte_arr.seek(0)
            base64_string = base64.b64encode(img_byte_arr.read()).decode(
                "utf-8"
            )
            return f"data:image/{(src.format or 'png').lower()};base64,{base64_string}"

    # Handle NumPy arrays (convert to PNG)
    if DependencyManager.numpy.imported():
        import numpy as np

        if isinstance(src, np.ndarray):
            if DependencyManager.pillow.imported():
                from PIL import Image

                img = Image.fromarray(np.uint8(src))
                return io_to_data_url(img, "image/png")

    # Handle pathlib.Path
    if isinstance(src, pathlib.Path):
        return io_to_data_url(src.read_bytes(), fallback_mime_type)

    # Handle strings - check if it's a URL
    if isinstance(src, str):
        parsed = urlparse(src)
        if parsed.scheme and parsed.netloc:
            return src  # Return URLs as-is

        # Try to open as a file path
        try:
            with open(src, "rb") as f:
                return io_to_data_url(f, fallback_mime_type)
        except (OSError, FileNotFoundError):
            return src

    # Handle Pandas DataFrames (convert to CSV)
    if can_narwhalify(src, eager_only=True):
        df = nw.from_native(src, pass_through=False, eager_only=True)
        file = io.BytesIO()
        df.write_csv(file)
        file.seek(0)
        return io_to_data_url(file, "text/csv")

    return str(src)


def is_data_empty(data: Union[str, bytes, io.BytesIO, Any]) -> bool:
    """Check if a data object is empty."""
    if isinstance(data, str):
        return data == ""

    if isinstance(data, bytes):
        return data == b""

    if hasattr(data, "getbuffer"):
        return cast(io.BytesIO, data).getbuffer().nbytes == 0

    return False
