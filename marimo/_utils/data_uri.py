# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import base64


def build_data_url(mimetype: str, data: bytes) -> str:
    assert mimetype is not None
    # `data` must be base64 encoded
    str_repr = data.decode("utf-8").replace("\n", "")
    return f"data:{mimetype};base64,{str_repr}"


# Format: data:mime_type;base64,data
def from_data_uri(data: str) -> tuple[str, bytes]:
    assert isinstance(data, str)
    assert data.startswith("data:")
    mime_type, data = data.split(",", 1)
    # strip data: and ;base64
    mime_type = mime_type.split(";")[0][5:]
    return mime_type, base64.b64decode(data)
