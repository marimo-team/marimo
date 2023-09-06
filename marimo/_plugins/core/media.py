# Copyright 2023 Marimo. All rights reserved.
import base64
import io
import mimetypes
from typing import Optional, Union


def guess_mime_type(src: Union[str, bytes, io.BytesIO, None]) -> Optional[str]:
    """Guess the MIME type of a file."""
    if src is None:
        return None

    if isinstance(src, str) and src.startswith("data:"):
        return src.split(";")[0].split(":")[1]

    if isinstance(src, str):
        return mimetypes.guess_type(src)[0]

    if isinstance(src, io.FileIO):
        return mimetypes.guess_type(src.name)[0]

    return None


def io_to_data_url(
    src: Union[str, bytes, io.BytesIO, None], fallback_mime_type: str
) -> Optional[str]:
    """Convert a file-like object to a data URL."""
    if src is None:
        return None

    if isinstance(src, io.BytesIO):
        # clone before reading, so we don't consume the stream
        src = io.BytesIO(src.getvalue())
        base64_string = base64.b64encode(src.read()).decode("utf-8")
        file_type = guess_mime_type(src) or fallback_mime_type
        return f"data:{file_type};base64,{base64_string}"

    if isinstance(src, bytes):
        base64_string = base64.b64encode(src).decode("utf-8")
        return f"data:{fallback_mime_type};base64,{base64_string}"

    return src


def is_data_empty(data: Union[str, bytes, io.BytesIO]) -> bool:
    """Check if a data object is empty."""
    if isinstance(data, str):
        return data == ""

    if isinstance(data, bytes):
        return data == b""

    if isinstance(data, io.BytesIO):
        return data.getbuffer().nbytes == 0

    return False
