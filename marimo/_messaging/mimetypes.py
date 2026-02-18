# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Literal, Union

# It is convenient to write mimetypes as strings,
# but can lead to typos. This literal type helps
# us avoid typos.
#
# While nonstandard MIME types are often given an
# `x-` prefix our non IAIA types to not follow
# this convention (e.g., text/password, text/latex).
KnownMimeType = Literal[
    "application/json",
    "application/vnd.marimo+error",
    "application/vnd.marimo+traceback",
    "application/vnd.marimo+mimebundle",
    "application/vnd.vega.v5+json",
    "application/vnd.vegalite.v5+json",
    "application/vnd.vega.v6+json",
    "application/vnd.vegalite.v6+json",
    "application/vnd.jupyter.widget-view+json",
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
    "text/password",
    "text/markdown",
    "text/latex",
    "text/csv",
]

ConsoleMimeType = Literal[
    "application/vnd.marimo+traceback",
    "text/plain",
    "text/password",
    "image/png",
]

MimeBundle = dict[KnownMimeType, Any]
MimeBundleTuple = tuple[KnownMimeType, Any]
MimeBundleOrTuple = Union[MimeBundle, MimeBundleTuple]

# Used for metadata in a marimo mimebundle
METADATA_KEY = "__metadata__"
