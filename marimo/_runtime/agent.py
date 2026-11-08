# Copyright 2026 Marimo. All rights reserved.
"""Per-kernel agent state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._types.ids import CellId_t


@dataclass
class Agent:
    """One per `Kernel` — long-lived across scratchpad executions."""

    read_etags: dict[CellId_t, str] = field(default_factory=dict)
