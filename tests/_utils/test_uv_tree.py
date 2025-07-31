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
def test_empty_script_tree_stable_output(tmp_path: pathlib.Path) -> None:
    script_path = tmp_path / "blah.py"
    uv(["init", "--script", str(script_path)])
    raw = uv(["tree", "--no-dedupe", "--script", str(script_path)])
    tree = parse_uv_tree(raw)
    snapshot_test("empty_script_tree.json", serialize(tree))


def test_complex_project_tree_raw_snapshot() -> None:
    raw = """blah v0.1.0
├── anywidget v0.9.18
│   ├── ipywidgets v8.1.7
│   │   ├── comm v0.2.2
│   │   │   └── traitlets v5.14.3
│   │   ├── ipython v9.3.0
│   │   │   ├── decorator v5.2.1
│   │   │   ├── ipython-pygments-lexers v1.1.1
│   │   │   │   └── pygments v2.19.1
│   │   │   ├── jedi v0.19.2
│   │   │   │   └── parso v0.8.4
│   │   │   ├── matplotlib-inline v0.1.7
│   │   │   │   └── traitlets v5.14.3
│   │   │   ├── pexpect v4.9.0
│   │   │   │   └── ptyprocess v0.7.0
│   │   │   ├── prompt-toolkit v3.0.51
│   │   │   │   └── wcwidth v0.2.13
│   │   │   ├── pygments v2.19.1
│   │   │   ├── stack-data v0.6.3
│   │   │   │   ├── asttokens v3.0.0
│   │   │   │   ├── executing v2.2.0
│   │   │   │   └── pure-eval v0.2.3
│   │   │   └── traitlets v5.14.3
│   │   ├── jupyterlab-widgets v3.0.15
│   │   ├── traitlets v5.14.3
│   │   └── widgetsnbextension v4.0.14
│   ├── psygnal v0.13.0
│   └── typing-extensions v4.14.0
├── marimo v0.0.0
│   ├── click v8.2.1
│   ├── docutils v0.21.2
│   ├── itsdangerous v2.2.0
│   ├── jedi v0.19.2
│   │   └── parso v0.8.4
│   ├── loro v1.5.1
│   ├── markdown v3.8.1
│   ├── narwhals v1.42.1
│   ├── packaging v25.0
│   ├── psutil v7.0.0
│   ├── pygments v2.19.1
│   ├── pymdown-extensions v10.15
│   │   ├── markdown v3.8.1
│   │   └── pyyaml v6.0.2
│   ├── pyyaml v6.0.2
│   ├── starlette v0.47.0
│   │   └── anyio v4.9.0
│   │       ├── idna v3.10
│   │       └── sniffio v1.3.1
│   ├── tomlkit v0.13.3
│   ├── uvicorn v0.34.3
│   │   ├── click v8.2.1
│   │   └── h11 v0.16.0
│   └── websockets v15.0.1
├── pandas v2.3.0 (extra: bar)
│   ├── numpy v2.3.0
│   ├── python-dateutil v2.9.0.post0
│   │   └── six v1.17.0
│   ├── pytz v2025.2
│   └── tzdata v2025.2
└── pytest v8.4.1 (group: dev)
    ├── iniconfig v2.1.0
    ├── packaging v25.0
    ├── pluggy v1.6.0
    └── pygments v2.19.1"""
    tree = parse_uv_tree(raw)
    snapshot_test("complex_project_tree_from_raw.json", serialize(tree))


def test_script_tree_raw_snapshot() -> None:
    raw = """polars v1.31.0
pandas v2.3.0
├── numpy v2.3.0
├── python-dateutil v2.9.0.post0
│   └── six v1.17.0
├── pytz v2025.2
└── tzdata v2025.2
anywidget v0.9.18
├── ipywidgets v8.1.7
│   ├── comm v0.2.2
│   │   └── traitlets v5.14.3
│   ├── ipython v9.3.0
│   │   ├── decorator v5.2.1
│   │   ├── ipython-pygments-lexers v1.1.1
│   │   │   └── pygments v2.19.1
│   │   ├── jedi v0.19.2
│   │   │   └── parso v0.8.4
│   │   ├── matplotlib-inline v0.1.7
│   │   │   └── traitlets v5.14.3
│   │   ├── pexpect v4.9.0
│   │   │   └── ptyprocess v0.7.0
│   │   ├── prompt-toolkit v3.0.51
│   │   │   └── wcwidth v0.2.13
│   │   ├── pygments v2.19.1
│   │   ├── stack-data v0.6.3
│   │   │   ├── asttokens v3.0.0
│   │   │   ├── executing v2.2.0
│   │   │   └── pure-eval v0.2.3
│   │   └── traitlets v5.14.3
│   ├── jupyterlab-widgets v3.0.15
│   ├── traitlets v5.14.3
│   └── widgetsnbextension v4.0.14
├── psygnal v0.13.0
└── typing-extensions v4.14.0"""
    tree = parse_uv_tree(raw)
    snapshot_test("script_tree_from_raw.json", serialize(tree))
