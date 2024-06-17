# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._ast.cell import CellId_t


def is_mangled_local(name: str, cell_id: CellId_t) -> bool:
    return name.startswith(f"_cell_{cell_id}")


def is_local(name: str) -> bool:
    return name.startswith("_") and not name.startswith("__")
