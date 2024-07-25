# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._ast.cell import CellId_t


def is_local_then_mangle(ref: str, cell_id: CellId_t) -> str:
    if is_local(ref):
        if ref.startswith("_cell"):
            return ref
        return f"_cell_{cell_id}{ref}"
    return ref


def unmangle_local(name: str) -> tuple[str, str]:
    if not is_mangled_local(name):
        return name, ""
    return re.sub(r"^_cell_\w+_", "_", name), name.split("_")[2]


def is_mangled_local(name: str, cell_id: CellId_t = "") -> bool:
    return name.startswith(f"_cell_{cell_id}")


def is_local(name: str) -> bool:
    return name == "__" or (name.startswith("_") and not name.startswith("__"))
