from __future__ import annotations

import json
import pathlib

import pytest

from marimo._ast.app import InternalApp
from marimo._ast.load import load_app
from marimo._convert.ipynb import convert_from_ir_to_ipynb
from tests.mocks import snapshotter

SELF_DIR = pathlib.Path(__file__).parent
snapshot_test = snapshotter(__file__)


@pytest.mark.parametrize(
    "py_path", (SELF_DIR / "fixtures" / "py").glob("*.py")
)
def test_convert_from_ir_to_ipynb_snapshots(py_path: pathlib.Path) -> None:
    """Test convert_from_ir_to_ipynb against all Python fixtures using snapshots."""
    # Load the marimo app from file
    app = load_app(py_path)
    assert app
    internal_app = InternalApp(app)

    # Convert
    sort_mode = "top-down"
    ipynb_str = convert_from_ir_to_ipynb(internal_app, sort_mode=sort_mode)

    # Parse as JSON to validate and format consistently
    ipynb_json = json.loads(ipynb_str)
    formatted_ipynb = json.dumps(ipynb_json, indent=2, sort_keys=True)

    base_name = py_path.name.replace(".py", "")
    snapshot_name = f"{base_name}_{sort_mode.replace('-', '_')}.ipynb.txt"

    snapshot_test(snapshot_name, formatted_ipynb)
