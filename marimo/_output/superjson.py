# Copyright 2026 Marimo. All rights reserved.
# This data serializes
from __future__ import annotations

from typing import Any


class SuperJson:  # noqa: B903
    """
    This class bypasses the default msgspec encoder for the data provided and instead serializes
    the result to something that is more human readable and not information-lossy.

    The key differences from the default msgspec encoder are:
    - It serializes the b'hello' to 'hello' instead of base64 encoded
    - It serializes the float('inf') to Infinity instead of null
    - It serializes the float('nan') to NaN instead of null
    - It serializes the timedelta to a human readable string instead of a ISO 8601 duration (e.g. "1 day, 2:03:00")
    """

    def __init__(self, data: Any):
        self.data = data

    def _marimo_serialize_(self) -> Any:
        from marimo._messaging.msgspec_encoder import enc_hook

        return enc_hook(self.data)
