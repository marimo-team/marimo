# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Union

import msgspec

# Values that round-trip through the IPC msgspec encoder.
Encodable = Union[
    None,
    bool,
    int,
    float,
    str,
    bytes,
    list["Encodable"],
    tuple["Encodable", ...],
    dict[str, "Encodable"],
    msgspec.Struct,
]
