"""Snapshot tests for ipynb export functionality."""

from __future__ import annotations

import pathlib
import sys
from pathlib import Path

import pytest

from marimo._ast.app import InternalApp
from marimo._ast.load import load_app
from marimo._convert.ipynb.from_ir import convert_from_ir_to_ipynb
from marimo._dependencies.dependencies import DependencyManager
from marimo._server.export import run_app_then_export_as_ipynb
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

pytest.importorskip("nbformat")


def _load_fixture_app(path: Path | str) -> InternalApp:
    """Load a fixture app by name."""
    if isinstance(path, str):
        path = FIXTURES_DIR / f"{path}.py"
    app = load_app(path)
    assert app is not None
    return InternalApp(app)


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
    result = await run_app_then_export_as_ipynb(
        MarimoPath(app_path),
        sort_mode="top-down",
        cli_args={},
        argv=None,
    )
    assert result.download_filename == f"{app_path.stem}.ipynb"
    content = delete_lines_with_files(result.text)
    content = simplify_images(content)
    snapshot(f"ipynb/{app_path.stem}.ipynb.txt", content)
