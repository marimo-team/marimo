# Copyright 2025 Marimo. All rights reserved.
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CellVariableValue:
    name: str
    # Cell variables can be arbitrary Python values (int, str, list, dict, ...),
    # so we keep this as Any to reflect actual runtime.
    value: Optional[Any] = None
    data_type: Optional[str] = None
