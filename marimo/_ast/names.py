# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

DEFAULT_CELL_NAME = "_"
SETUP_CELL_NAME = "setup"
# Intentionally an invalid name character
TOPLEVEL_CELL_PREFIX = "*"


def is_internal_cell_name(name: str) -> bool:
    # Include "__" (for backwards compatibility)
    return name == DEFAULT_CELL_NAME or name == "__"
