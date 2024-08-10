# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import TYPE_CHECKING

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


def unmangle_local(name: str) -> UnmagledLocal:
    if not is_mangled_local(name):
        return UnmagledLocal(name, "")
    return UnmagledLocal(re.sub(r"^_cell_\w+", "_", name), name[6:10])


def is_mangled_local(name: str, cell_id: CellId_t = "") -> bool:
    return name.startswith(f"_cell_{cell_id}")


def is_local(name: str) -> bool:
    return name == "__" or (name.startswith("_") and not name.startswith("__"))
