# Copyright 2024 Marimo. All rights reserved.
from typing import Literal

# It is convenient to write mimetypes a string,
# but can lead to typos. This literal type
# helps us avoid typos.
KnownMimeType = Literal[
    "text/plain",
    "text/html",
    "application/vnd.marimo+error",
    "application/json",
]
