# Copyright 2026 Marimo. All rights reserved.
"""Decide what each cell becomes in the compiled notebook.

The build pipeline runs in three phases:

1. **Static classification** (:mod:`marimo._build.classify`): split cells
   into ``compilable`` and ``non_compilable`` based on the AST. A cell
   is compilable iff none of its ancestors directly references a
   runtime input (``mo.ui.*``, ``mo.cli_args``).

2. **Execution** (:mod:`marimo._build.runner`): run every statically
   compilable cell, capturing its defs.

3. **Planning** (this module): turn the post-execution facts — which
   cells defined globals at all, which ones produced persistable
   values — into a per-cell :class:`CellKind`.

The rule, written inductively:

.. code-block::

    compilable(c) ⟺ static_compilable(c) ∧ has_defs(c) ∧ persistable(c)
    named(c)     ⟺ c.fn_name does not start with "_"
    retained_consumer(c) ⟺ c.defs ∩ ⋃{d.refs : kind(d) ∈ {SETUP, VERBATIM}} ≠ ∅

    kind(c) =
        SETUP                     if c is the setup cell
        LOADER                    if compilable(c) ∧ (named(c) ∨ retained_consumer(c))
        ELIDED                    if compilable(c) ∧ ¬named(c) ∧ ¬retained_consumer(c)
        VERBATIM                  otherwise

This is a single pass: ELIDED cells contribute nothing to retained refs
(they're gone from the output), and LOADER cells contribute only helper
names — never user-defined names — so resolving a cell's kind never
needs to revisit another cell's decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from marimo._build.serialize import classify_value

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from marimo._ast.cell_manager import CellManager
    from marimo._build.classify import Classification
    from marimo._build.serialize import ArtifactKind
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._types.ids import CellId_t


class CellKind(Enum):
    """How a cell appears in the compiled notebook."""

    SETUP = "setup"
    """The (single) ``with app.setup`` block, kept verbatim at the top."""

    LOADER = "loader"
    """Replaced with a tiny loader that reads its precomputed artifact."""

    ELIDED = "elided"
    """Removed from the output entirely — its value is no longer needed."""

    VERBATIM = "verbatim"
    """Source preserved unchanged; runs at notebook load time."""


@dataclass(frozen=True)
class CellPlan:
    """Per-cell decision, emitted by :func:`compute_plan`."""

    kind: CellKind
    # For LOADER cells: the persistable defs in their original order
    # (def_name, artifact_kind). Empty for everything else.
    loader_defs: tuple[tuple[str, ArtifactKind], ...] = ()


@dataclass(frozen=True)
class Plan:
    """The full per-cell plan for one build."""

    cells: Mapping[CellId_t, CellPlan]

    def kind(self, cell_id: CellId_t) -> CellKind:
        return self.cells[cell_id].kind


def compute_plan(
    *,
    graph: DirectedGraph,
    cell_manager: CellManager,
    classification: Classification,
    captured_defs: Mapping[CellId_t, Mapping[str, Any]],
) -> Plan:
    """Decide every cell's :class:`CellKind` in a single pass.

    Parameters
    ----------
    captured_defs:
        Mapping from cell id to the globals the cell defined when it
        ran in the build runner. Cells that weren't executed (or
        weren't statically compilable) may be absent.
    """
    setup_id = cell_manager.setup_cell_id

    # Step 1 — runtime-compilable: cells that ran cleanly AND defined at
    # least one global AND every def is persistable.
    runtime_compilable: dict[
        CellId_t, tuple[tuple[str, ArtifactKind], ...]
    ] = {}
    for cid in classification.compilable:
        defs = captured_defs.get(cid, {})
        if not defs:
            # Side-effect-only cells (display, prints, mutation): no
            # value to materialize — always emit verbatim.
            continue
        kinds: list[tuple[str, ArtifactKind]] = []
        for name, value in defs.items():
            artifact_kind = classify_value(value)
            if artifact_kind is None:
                kinds = []
                break
            kinds.append((name, artifact_kind))
        if kinds:
            runtime_compilable[cid] = tuple(kinds)

    # Step 2 — retained refs: refs of every cell that ends up SETUP or
    # VERBATIM in the output. A cell is VERBATIM iff it's not the setup
    # cell and isn't runtime-compilable.
    retained_refs: set[str] = set()
    for cid, cell in graph.cells.items():
        if cid == setup_id or cid not in runtime_compilable:
            retained_refs |= cell.refs

    # Step 3 — assign a kind to every cell.
    cells: dict[CellId_t, CellPlan] = {}
    for cid, cell in graph.cells.items():
        if cid == setup_id:
            cells[cid] = CellPlan(kind=CellKind.SETUP)
        elif cid in runtime_compilable:
            named = not cell_manager.cell_name(cid).startswith("_")
            retained_consumer = bool(cell.defs & retained_refs)
            if named or retained_consumer:
                cells[cid] = CellPlan(
                    kind=CellKind.LOADER,
                    loader_defs=runtime_compilable[cid],
                )
            else:
                cells[cid] = CellPlan(kind=CellKind.ELIDED)
        else:
            cells[cid] = CellPlan(kind=CellKind.VERBATIM)
    return Plan(cells=cells)
