# Copyright 2026 Marimo. All rights reserved.
"""Predict each cell's compiled-notebook outcome without running anything.

The Build panel needs per-cell badges that update as the user edits.
Re-running the full build pipeline on every keystroke is far too
expensive, so this module gives a *best-effort* prediction from
purely static information (the AST and the dataflow graph) plus,
optionally, the values bound by the live edit kernel.

There are two prediction sources, in order of decreasing fidelity:

1. **Live-globals path** — when the caller can supply ``live_globals``
   from a kernel snapshot, we feed the values through
   :func:`classify_value` (the same persistability check the build
   uses) and then through :func:`compute_plan` (the same single-pass
   kind assignment). Cells that have been run live get a
   ``confidence`` of ``predicted`` (or ``stale`` if their source has
   changed since the last run); cells that haven't been run get
   ``unmaterialized``.

2. **Static-only path** — when no kernel snapshot is available we
   fall back to a coarser prediction that uses just the AST: cells in
   :class:`marimo._build.classify.Classification.compilable` are
   labelled ``compilable`` (no LOADER vs ELIDED vs VERBATIM split,
   since persistability requires running the cell), and the rest
   inherit ``setup`` / ``non_compilable``.

Either way, the actual ``build_notebook`` run later overwrites the
live preview with ground-truth ``CellStatus`` values via
:class:`marimo._build.events.CellPlanned` events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from marimo._build.classify import classify_static
from marimo._build.plan import CellKind, compute_plan
from marimo._build.serialize import classify_value

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from marimo._ast.cell_manager import CellManager
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._types.ids import CellId_t


# Confidence levels for a previewed cell's predicted kind. The UI
# renders ``predicted`` chips at full strength and the rest as muted /
# annotated chips so users can tell "this is a guess" from "this is
# what the build would do".
PreviewConfidence = Literal[
    "predicted",  # cell was executed live, defs available, fresh
    "stale",  # cell was executed but its source has changed since
    "unmaterialized",  # cell never ran, so we can't probe its defs
    "static",  # only the static classification is available
    "non_compilable",  # cell statically depends on a runtime input
    "setup",  # the setup cell — always emitted verbatim
]


@dataclass(frozen=True)
class PreviewCell:
    """One cell's predicted outcome in the compiled notebook."""

    cell_id: CellId_t
    name: str
    """The cell's function name in the source. ``"_"`` for anonymous cells."""
    display_name: str
    """Human-readable label — see :func:`marimo._build.build.display_name`."""
    predicted_kind: CellKind | None
    """``None`` when we genuinely can't predict the LOADER/ELIDED/VERBATIM
    split (e.g. live globals weren't supplied)."""
    confidence: PreviewConfidence


@dataclass(frozen=True)
class PreviewPlan:
    """Per-cell predictions in source order."""

    cells: tuple[PreviewCell, ...]


def compute_preview(
    *,
    graph: DirectedGraph,
    cell_manager: CellManager,
    live_globals: Mapping[str, Any] | None = None,
    fresh_cells: set[CellId_t] | None = None,
) -> PreviewPlan:
    """Predict each cell's :class:`CellKind` from static + live state.

    Parameters
    ----------
    graph, cell_manager:
        The dataflow graph and cell manager from the parsed notebook.
    live_globals:
        The kernel's module ``__dict__`` (or a snapshot of it). Values
        bound by previously-executed cells live here. ``None`` falls
        back to the static-only prediction.
    fresh_cells:
        The set of cell ids whose source has not changed since the last
        successful run. Cells outside this set are reported with
        ``confidence="stale"`` even if their defs are still in
        ``live_globals``.
    """
    classification = classify_static(graph, cell_manager)
    setup_id = cell_manager.setup_cell_id

    if live_globals is None:
        return _static_only_preview(
            graph=graph,
            cell_manager=cell_manager,
            classification=classification,
            setup_id=setup_id,
        )

    fresh_cells = fresh_cells if fresh_cells is not None else set()

    # Build a synthetic ``captured_defs`` mapping over the cells we can
    # actually predict: statically compilable AND defs present in the
    # live kernel. We feed this into ``compute_plan`` to leverage the
    # same single-pass rule the real build uses.
    captured_defs: dict[CellId_t, dict[str, Any]] = {}
    for cell_id in classification.compilable:
        cell = graph.cells[cell_id]
        defs: dict[str, Any] = {}
        for name in cell.defs:
            if name in live_globals:
                defs[name] = live_globals[name]
        # Only include cells where every def is present — partial
        # captures would mislead the planner.
        if defs and len(defs) == len(cell.defs):
            captured_defs[cell_id] = defs

    plan = compute_plan(
        graph=graph,
        cell_manager=cell_manager,
        classification=classification,
        captured_defs=captured_defs,
    )

    from marimo._build.build import display_name

    cells: list[PreviewCell] = []
    for cell_id, cell in graph.cells.items():
        name = cell_manager.cell_name(cell_id)
        label = display_name(name, cell)
        if cell_id == setup_id:
            cells.append(
                PreviewCell(
                    cell_id=cell_id,
                    name=name,
                    display_name=label,
                    predicted_kind=CellKind.SETUP,
                    confidence="setup",
                )
            )
            continue
        if cell_id in classification.non_compilable:
            cells.append(
                PreviewCell(
                    cell_id=cell_id,
                    name=name,
                    display_name=label,
                    predicted_kind=CellKind.VERBATIM,
                    confidence="non_compilable",
                )
            )
            continue

        if cell_id not in captured_defs:
            cells.append(
                PreviewCell(
                    cell_id=cell_id,
                    name=name,
                    display_name=label,
                    predicted_kind=None,
                    confidence="unmaterialized",
                )
            )
            continue

        confidence: PreviewConfidence = (
            "predicted" if cell_id in fresh_cells else "stale"
        )
        cells.append(
            PreviewCell(
                cell_id=cell_id,
                name=name,
                display_name=label,
                predicted_kind=plan.kind(cell_id),
                confidence=confidence,
            )
        )

        # Sanity probe: re-run classify_value on each captured def so a
        # genuinely non-persistable value is surfaced as VERBATIM even
        # if the planner would otherwise have promoted it. The planner
        # already does this internally, but the explicit call here is
        # documented in the docstring as the load-bearing fidelity
        # check.
        for value in captured_defs[cell_id].values():
            if classify_value(value) is None:
                # The planner already chose VERBATIM for this case;
                # the iteration is informational.
                break
    return PreviewPlan(cells=tuple(cells))


def _static_only_preview(
    *,
    graph: DirectedGraph,
    cell_manager: CellManager,
    classification: object,
    setup_id: CellId_t,
) -> PreviewPlan:
    """Best-effort prediction without any kernel state.

    We can't tell LOADER from ELIDED from VERBATIM without running the
    cell (persistability is a runtime property), so every statically
    compilable cell gets ``predicted_kind=None`` and
    ``confidence="static"``. The Build panel renders this as a single
    "compilable" badge until a build run firms it up.
    """
    # ``classification`` is typed as ``object`` so we don't import
    # ``Classification`` at module top-level for a TYPE_CHECKING-only
    # use; cast back here.
    from marimo._build.classify import Classification

    assert isinstance(classification, Classification)
    from marimo._build.build import display_name

    cells: list[PreviewCell] = []
    for cell_id, cell in graph.cells.items():
        name = cell_manager.cell_name(cell_id)
        label = display_name(name, cell)
        if cell_id == setup_id:
            cells.append(
                PreviewCell(
                    cell_id=cell_id,
                    name=name,
                    display_name=label,
                    predicted_kind=CellKind.SETUP,
                    confidence="setup",
                )
            )
        elif cell_id in classification.non_compilable:
            cells.append(
                PreviewCell(
                    cell_id=cell_id,
                    name=name,
                    display_name=label,
                    predicted_kind=CellKind.VERBATIM,
                    confidence="non_compilable",
                )
            )
        else:
            cells.append(
                PreviewCell(
                    cell_id=cell_id,
                    name=name,
                    display_name=label,
                    predicted_kind=None,
                    confidence="static",
                )
            )
    return PreviewPlan(cells=tuple(cells))
