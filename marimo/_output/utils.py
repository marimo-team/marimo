# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import urllib.parse
from typing import Optional, Union

from marimo._messaging.mimetypes import KnownMimeType


def build_data_url(mimetype: KnownMimeType, data: bytes) -> str:
    # `data` must be base64 encoded
    str_repr = data.decode("utf-8").replace("\n", "")
    return f"data:{mimetype};base64,{str_repr}"


def flatten_string(text: str) -> str:
    return "".join([line.strip() for line in text.split("\n")])


def create_style(
    pairs: dict[str, Union[str, int, float, None]],
) -> Optional[str]:
    if not pairs:
        return None

    return ";".join([f"{k}: {v}" for k, v in pairs.items() if v is not None])


def uri_encode_component(code: str) -> str:
    """Equivalent to `encodeURIComponent` in JavaScript."""
    return urllib.parse.quote(code, safe="~()*!.'")
