# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

# Values that round-trip through the IPC msgspec encoder.
# The recursive type definition breaks msgspec, but mypy is able to handle it and
# give us some garuntees.
if TYPE_CHECKING:
    import msgspec

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
else:
    Encodable = Any
