# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import mimetypes
import os
from pathlib import PurePath
from typing import Final
from urllib.parse import urlparse

_CUSTOM_MIME_TYPES: Final[dict[str, str]] = {
    ".toml": "application/toml",
}


def guess_mime_type(path: str | os.PathLike[str]) -> str | None:
    """Guess a file's MIME type consistently across platforms and processes."""
    path_string = os.fspath(path)
    parsed = urlparse(path_string)
    # A single-letter scheme is a Windows drive, not a URL.
    is_url = len(parsed.scheme) > 1 or (
        not parsed.scheme and bool(parsed.netloc)
    )
    mime_path = parsed.path if is_url else path_string
    suffix = PurePath(mime_path).suffix.lower()
    return _CUSTOM_MIME_TYPES.get(suffix) or mimetypes.guess_type(mime_path)[0]
