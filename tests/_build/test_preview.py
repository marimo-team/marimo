# Copyright 2026 Marimo. All rights reserved.
"""Static + live-globals preview tests.

Live-globals predictions need a notebook the runner has actually
executed; we leverage the existing build fixture (which executes
cleanly via ``build_notebook``) so we can compare predictions to the
ground-truth plan.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from marimo._ast.app import InternalApp
from marimo._ast.load import load_app
from marimo._build.classify import classify_static
from marimo._build.plan import CellKind
from marimo._build.preview import compute_preview
from marimo._build.runner import BuildRunner

pytest.importorskip("polars")
pytest.importorskip("duckdb")
pytest.importorskip("sqlglot")


FIXTURE = Path(__file__).parent / "fixtures" / "example_notebook.py"


def _load_internal() -> InternalApp:
    app = load_app(FIXTURE)
    assert app is not None
    return InternalApp(app)


def test_static_only_preview_buckets_cells_correctly() -> None:
    """Without live globals, predictions collapse to compilable / verbatim."""
    internal = _load_internal()
    plan = compute_preview(
        graph=internal.graph,
        cell_manager=internal.cell_manager,
    )
    by_name = {c.name: c for c in plan.cells}
    # Cells that depend on a runtime input are surfaced as VERBATIM
    # with full confidence — we don't need to run them to know.
    assert by_name["category"].confidence == "non_compilable"
    assert by_name["category"].predicted_kind is CellKind.VERBATIM
    assert by_name["filtered"].confidence == "non_compilable"
    # Statically compilable cells have no kind without a kernel value.
    assert by_name["customers"].confidence == "static"
    assert by_name["customers"].predicted_kind is None
    assert by_name["settings"].confidence == "static"


def test_live_globals_preview_matches_real_plan() -> None:
    """Feeding the runner's globals through the preview reproduces ``compute_plan``."""
    internal = _load_internal()
    classification = classify_static(internal.graph, internal.cell_manager)
    runner = BuildRunner(internal, classification)
    runner.run()

    # Reconstruct the live-globals dict the kernel would have.
    live_globals: dict[str, object] = {}
    for defs in runner.captured_defs.values():
        live_globals.update(defs)

    plan = compute_preview(
        graph=internal.graph,
        cell_manager=internal.cell_manager,
        live_globals=live_globals,
        fresh_cells=set(internal.cell_manager.valid_cell_ids()),
    )
    by_name = {c.name: c for c in plan.cells}

    # Same outcome categories as the real build:
    assert by_name["customers"].predicted_kind is CellKind.LOADER
    assert by_name["customers"].confidence == "predicted"
    assert by_name["settings"].predicted_kind is CellKind.LOADER
    # ``_users`` only feeds ``orders_enriched`` (now a loader), so the
    # planner elides it.
    assert by_name["_users"].predicted_kind is CellKind.ELIDED
    assert by_name["category"].predicted_kind is CellKind.VERBATIM


def test_unmaterialized_cells_get_unmaterialized_confidence() -> None:
    """Cells whose defs aren't in live_globals are flagged for the UI."""
    internal = _load_internal()
    # Empty live_globals mimics "cell never ran in the kernel".
    plan = compute_preview(
        graph=internal.graph,
        cell_manager=internal.cell_manager,
        live_globals={},
        fresh_cells=set(),
    )
    by_name = {c.name: c for c in plan.cells}
    assert by_name["customers"].confidence == "unmaterialized"
    assert by_name["customers"].predicted_kind is None


def test_stale_label_when_cell_not_in_fresh_set() -> None:
    """A cell whose defs are present but source has changed is ``stale``."""
    internal = _load_internal()
    classification = classify_static(internal.graph, internal.cell_manager)
    runner = BuildRunner(internal, classification)
    runner.run()
    live_globals: dict[str, object] = {}
    for defs in runner.captured_defs.values():
        live_globals.update(defs)

    plan = compute_preview(
        graph=internal.graph,
        cell_manager=internal.cell_manager,
        live_globals=live_globals,
        # No cells reported as fresh -> every prediction is "stale".
        fresh_cells=set(),
    )
    by_name = {c.name: c for c in plan.cells}
    assert by_name["customers"].confidence == "stale"
    # Categorical labels (setup/non_compilable) override stale.
    assert by_name["category"].confidence == "non_compilable"
