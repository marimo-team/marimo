# Copyright 2026 Marimo. All rights reserved.
"""Type definitions for dataflow graph."""

from __future__ import annotations

from marimo._types.ids import CellId_t

# Edge is a tuple of (parent, child) cell IDs
Edge = tuple[CellId_t, CellId_t]

# EdgeWithVar uses a tuple (not a set) for the variables linking the cells
# as sets are not JSON-serializable (required by static_notebook_template()).
# The first entry is the source node; the second entry is a tuple of defs from
# the source read by the destination; and the third entry is the destination
# node.
EdgeWithVar = tuple[CellId_t, tuple[str, ...], CellId_t]
