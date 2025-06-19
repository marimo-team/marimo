from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import subprocess

import pytest

from marimo._server.models.packages import DependencyTreeNode
from marimo._utils.uv_tree import parse_uv_tree
from tests.mocks import snapshotter

UV_BIN = os.environ.get("UV")
SELF_DIR = pathlib.Path(__file__).parent
snapshot_test = snapshotter(__file__)


def serialize(tree: DependencyTreeNode) -> str:
    return json.dumps(dataclasses.asdict(tree), indent=2)


def uv(cmd: list[str], cwd: str | None = None) -> str:
    assert UV_BIN, "Must have uv installed to use."
    result = subprocess.run(
        [UV_BIN] + cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=cwd,
        env={
            "UV_PYTHON": "3.13",
            "UV_EXCLUDE_NEWER": "2025-06-19T00:00:00-02:00",
        },
    )
    return result.stdout


@pytest.mark.skipif(UV_BIN is None, reason="requires uv executable.")
def test_complex_project_tree(tmp_path: pathlib.Path) -> None:
    uv(["init", "blah"], cwd=str(tmp_path))
    project_dir = tmp_path / "blah"
    uv(["add", "anywidget", "marimo"], cwd=str(project_dir))
    uv(["add", "--dev", "pytest"], cwd=str(project_dir))
    uv(["add", "--optional", "bar", "pandas"], cwd=str(project_dir))
    raw = uv(["tree", "--no-dedupe"], cwd=str(project_dir))
    tree = parse_uv_tree(raw)
    snapshot_test("complex_project_tree.json", serialize(tree))


@pytest.mark.skipif(UV_BIN is None, reason="requires uv executable.")
def test_empty_project_tree(tmp_path: pathlib.Path) -> None:
    uv(["init", "blah"], cwd=str(tmp_path))
    project_dir = tmp_path / "blah"
    raw = uv(["tree", "--no-dedupe"], cwd=str(project_dir))
    tree = parse_uv_tree(raw)
    snapshot_test("empty_project_tree.json", serialize(tree))


@pytest.mark.skipif(UV_BIN is None, reason="requires uv executable.")
def test_simple_project_tree(tmp_path: pathlib.Path) -> None:
    uv(["init", "blah"], cwd=str(tmp_path))
    project_dir = tmp_path / "blah"
    uv(["add", "polars", "pandas"], cwd=str(project_dir))
    raw = uv(["tree", "--no-dedupe"], cwd=str(project_dir))
    tree = parse_uv_tree(raw)
    snapshot_test("simple_project_tree.json", serialize(tree))


@pytest.mark.skipif(UV_BIN is None, reason="requires uv executable.")
def test_script_tree(tmp_path: pathlib.Path) -> None:
    script_path = tmp_path / "blah.py"
    uv(["init", "--script", str(script_path)])
    uv(["add", "--script", str(script_path), "polars", "pandas", "anywidget"])
    raw = uv(["tree", "--no-dedupe", "--script", str(script_path)])
    tree = parse_uv_tree(raw)
    snapshot_test("script_tree.json", serialize(tree))


@pytest.mark.skipif(UV_BIN is None, reason="requires uv executable.")
def test_empty_script_tree(tmp_path: pathlib.Path) -> None:
    script_path = tmp_path / "blah.py"
    uv(["init", "--script", str(script_path)])
    raw = uv(["tree", "--no-dedupe", "--script", str(script_path)])
    tree = parse_uv_tree(raw)
    snapshot_test("empty_script_tree.json", serialize(tree))
