# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import msgspec

from marimo._types.ids import CellId_t, UIElementId


class UpdateUIElementValuesRequest(msgspec.Struct, rename="camel"):
    object_ids: list[UIElementId]
    values: list[Any]

    # Validate same length
    def __post_init__(self) -> None:
        assert len(self.object_ids) == len(self.values), (
            "Mismatched object_ids and values"
        )


class InstantiateNotebookRequest(UpdateUIElementValuesRequest):
    auto_run: bool = True
    # Optional: cell codes to use instead of the codes from the file.
    # This is used when the frontend has local edits that should be
    # used instead of the file codes (e.g., pre-connect editing).
    # Maps cell_id -> code.
    codes: dict[CellId_t, str] | None = None
