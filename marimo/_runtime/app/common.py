# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._ast.cell import CellId_t

OutputsType = dict[CellId_t, Any]
DefsType = dict[str, Any]

RunOutput = tuple[OutputsType, DefsType]
