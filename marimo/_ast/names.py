# Copyright 2024 Marimo. All rights reserved.
DEFAULT_CELL_NAME = "_"


def is_internal_cell_name(name: str) -> bool:
    # Include "__" (for backwards compatibility)
    return name == DEFAULT_CELL_NAME or name == "__"
