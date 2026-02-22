from __future__ import annotations

import pathlib

import pytest

from marimo._ast.app import InternalApp
from marimo._ast.load import load_app
from marimo._convert.converters import MarimoConvert
from marimo._convert.ipynb import (
    convert_from_ipynb_to_notebook_ir,
    convert_from_ir_to_ipynb,
)

SELF_DIR = pathlib.Path(__file__).parent

IPYNB_FIXTURES = (SELF_DIR / "fixtures" / "ipynb").glob("*.ipynb")
PY_FIXTURES = (SELF_DIR / "fixtures" / "py").glob("*.py")


@pytest.mark.parametrize("py_path", PY_FIXTURES)
def test_iypnb_idempotent(py_path: pathlib.Path) -> None:
    py_contents = py_path.read_text()
    app = load_app(py_path)
    assert app
    internal_app = InternalApp(app)
    ipynb_str = convert_from_ir_to_ipynb(internal_app, sort_mode="top-down")
    ir = convert_from_ipynb_to_notebook_ir(ipynb_str)
    assert py_contents == MarimoConvert.from_ir(ir).to_py()
