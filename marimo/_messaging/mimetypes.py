# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Literal, Union

# It is convenient to write mimetypes as strings,
# but can lead to typos. This literal type
# helps us avoid typos.
KnownMimeType = Literal[
    "application/json",
    "application/vnd.marimo+error",
    "application/vnd.marimo+traceback",
    "application/vnd.marimo+mimebundle",
    "application/vnd.vega.v5+json",
    "application/vnd.vegalite.v5+json",
    "image/png",
    "image/svg+xml",
    "image/tiff",
    "image/avif",
    "image/bmp",
    "image/gif",
    "image/jpeg",
    "video/mp4",
    "video/mpeg",
    "text/html",
    "text/plain",
    "text/markdown",
    "text/latex",
    "text/csv",
]

ConsoleMimeType = Literal[
    "application/vnd.marimo+traceback",
    "text/plain",
    "image/png",
]

MimeBundle = dict[KnownMimeType, Any]
MimeBundleOrTuple = Union[MimeBundle, tuple[MimeBundle, Any]]
