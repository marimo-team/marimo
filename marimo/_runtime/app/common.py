# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Dict, Tuple

from marimo._types.ids import CellId_t

OutputsType = Dict[CellId_t, Any]
DefsType = Dict[str, Any]

RunOutput = Tuple[OutputsType, DefsType]
