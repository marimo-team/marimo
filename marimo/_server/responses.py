# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import starlette.responses

from marimo._messaging.msgspec_encoder import encode_json_bytes

if TYPE_CHECKING:
    import msgspec


class StructResponse(starlette.responses.Response):
    media_type = "application/json"

    def __init__(self, struct: msgspec.Struct) -> None:
        super().__init__(content=encode_json_bytes(struct))
