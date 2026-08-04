"""Snapshot tests for ipynb export functionality."""

from __future__ import annotations

import pathlib
import sys
from pathlib import Path

import pytest

from marimo._ast.app import App, InternalApp
from marimo._ast.cell import CellConfig
from marimo._ast.load import load_app
from marimo._convert.ipynb.from_ir import convert_from_ir_to_ipynb
from marimo._dependencies.dependencies import DependencyManager
from marimo._export.file import export_ipynb
from marimo._export.requests import (
    IPYNBFileExportRequest,
    NotebookExecutionOptions,
)
from marimo._schemas.export_options import IPYNBExportOptions
from marimo._types.ids import CellId_t
from marimo._utils.marimo_path import MarimoPath
from tests.mocks import delete_lines_with_files, simplify_images, snapshotter

SELF_DIR = pathlib.Path(__file__).parent
FIXTURES_DIR = SELF_DIR / "fixtures" / "apps"
snapshot = snapshotter(__file__)

HAS_DEPS = (
    DependencyManager.polars.has()
    and DependencyManager.altair.has()
    and DependencyManager.matplotlib.has()
)

nbformat = pytest.importorskip("nbformat")


def _load_fixture_app(path: Path | str) -> InternalApp:
    """Load a fixture app by name."""
    if isinstance(path, str):
        path = FIXTURES_DIR / f"{path}.py"
    app = load_app(path)
    assert app is not None
    return InternalApp(app)


def test_topological_export_preserves_invalid_cells() -> None:
    app = App()

    @app.cell()
    def _():
        valid = 1
        return (valid,)

    internal_app = InternalApp(app)
    valid_cell = next(iter(internal_app.cell_manager.cell_data()))
    _ = internal_app.graph
    internal_app.with_data(
        cell_ids=[CellId_t("invalid-cell"), valid_cell.cell_id],
        codes=["x =", valid_cell.code],
        names=["_", valid_cell.name],
        configs=[CellConfig(), valid_cell.config],
    )
    assert not internal_app.cell_manager.unparsable

    notebook = nbformat.reads(
        convert_from_ir_to_ipynb(internal_app, sort_mode="topological"),
        as_version=4,
    )

    assert [cell.source for cell in notebook.cells] == ["x =", valid_cell.code]


# Apps with heavy dependencies (matplotlib, pandas, polars, etc) that timeout in CI
HEAVY_DEPENDENCY_APPS = {"with_outputs"}


@pytest.mark.parametrize(
    "app_path",
    [
        path
        for path in FIXTURES_DIR.glob("*.py")
        if path.stem not in HEAVY_DEPENDENCY_APPS
    ],
    ids=lambda path: path.stem,
)
@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.skipif(
    sys.version_info < (3, 11), reason="3.10 has different stack trace format"
)
async def test_export_ipynb(app_path: Path) -> None:
    """Test ipynb export with actual execution outputs."""
    internal_app = _load_fixture_app(app_path)

    # Test without session view
    content = convert_from_ir_to_ipynb(
        internal_app, sort_mode="top-down", session_view=None
    )
    assert content is not None

    # Test with actual run
    result = await export_ipynb(
        IPYNBFileExportRequest(
            path=MarimoPath(app_path),
            options=IPYNBExportOptions(sort_mode="top-down"),
            execution=NotebookExecutionOptions(cli_args={}, argv=None),
        )
    )
    assert result.download_filename == f"{app_path.stem}.ipynb"
    content = delete_lines_with_files(result.text)
    content = simplify_images(content)
    snapshot(f"ipynb/{app_path.stem}.ipynb.txt", content)
