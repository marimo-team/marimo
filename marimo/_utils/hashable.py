# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations


def is_hashable(*values: object) -> bool:
    """
    Check if all values passed in are hashable.
    """
    try:
        hash(values)
        return True
    except TypeError:
        return False
