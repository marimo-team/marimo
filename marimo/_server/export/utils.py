# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Optional
from urllib.parse import quote


def get_filename(filename: Optional[str], default: str = "notebook.py") -> str:
    if not filename:
        filename = default
    return filename


def get_download_filename(filename: Optional[str], extension: str) -> str:
    filename = filename or f"notebook.{extension}"
    basename = os.path.basename(filename)
    if basename.endswith(f".{extension}"):
        return basename
    return f"{os.path.splitext(basename)[0]}.{extension}"


def make_download_headers(filename: str) -> dict[str, str]:
    """Create headers for file download with proper Content-Disposition encoding.

    This function handles non-ASCII filenames using RFC 5987 encoding
    (filename*=UTF-8''...) to avoid UnicodeEncodeError when the filename
    contains characters outside the Latin-1 range.

    Args:
        filename: The filename for the download (may contain non-ASCII chars)

    Returns:
        A dict with the Content-Disposition header properly encoded
    """
    # URL-encode the filename for RFC 5987 (preserves safe chars like .)
    encoded_filename = quote(filename, safe="")

    # Use RFC 5987 encoding: filename*=UTF-8''<url-encoded-filename>
    # Also provide a fallback ASCII filename for older clients
    return {
        "Content-Disposition": (
            f"attachment; filename*=UTF-8''{encoded_filename}"
        )
    }
