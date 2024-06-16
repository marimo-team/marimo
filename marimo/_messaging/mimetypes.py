# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import Literal

if sys.version_info < (3, 10):
    from typing_extensions import Annotated, TypeAlias
else:
    from typing import Annotated, TypeAlias

# It is convenient to write mimetypes as strings,
# but can lead to typos. This literal type
# helps us avoid typos.
KnownMimeType: TypeAlias = Annotated[
    Literal[
        "application/json",
        "application/vnd.marimo+error",
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
        "text/csv",
    ],
    "MimeType",
]
