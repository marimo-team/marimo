# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any


def is_hashable(*values: Any) -> bool:
    """
    Check if all values passed in are hashable.
    """
    try:
        hash(values)
        return True
    except TypeError:
        return False
