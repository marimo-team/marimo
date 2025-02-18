# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from marimo._ast.cell import CellId_t


from collections import namedtuple

UnmagledLocal = namedtuple("UnmagledLocal", "name cell")


def if_local_then_mangle(ref: str, cell_id: CellId_t) -> str:
    if is_local(ref):
        if is_mangled_local(ref):
            return ref
        return f"_cell_{cell_id}{ref}"
    return ref


def unmangle_local(name: str, cell_id: CellId_t = "") -> UnmagledLocal:
    if not is_mangled_local(name, cell_id):
        return UnmagledLocal(name, "")
    private_prefix = r"^_cell_\w+?_"
    if cell_id:
        private_prefix = f"^_cell_{cell_id}_"
    return UnmagledLocal(re.sub(private_prefix, "_", name), name.split("_")[2])


def is_mangled_local(name: str, cell_id: CellId_t = "") -> bool:
    return name.startswith(f"_cell_{cell_id}")


def is_local(name: str) -> bool:
    return name == "__" or (name.startswith("_") and not name.startswith("__"))


def get_cell_from_local(
    name: str, cell_id: CellId_t = ""
) -> Optional[CellId_t]:
    local = unmangle_local(if_local_then_mangle(name, cell_id)).cell
    return local if local else None
