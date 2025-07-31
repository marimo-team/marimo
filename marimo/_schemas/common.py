# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import TypedDict


# Base types for extensibility
class BaseDict(TypedDict, total=False):
    """Base dictionary allowing additional fields"""

    pass
