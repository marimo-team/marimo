from __future__ import annotations

import pathlib

import pytest

pytest.importorskip("nbformat")

from marimo import __version__
from marimo._ast.app import InternalApp
from marimo._ast.load import load_app
from marimo._convert.converters import MarimoConvert
from marimo._convert.ipynb import (
    convert_from_ipynb_to_notebook_ir,
    convert_from_ir_to_ipynb,
)

SELF_DIR = pathlib.Path(__file__).parent
FIXTURES_PY = SELF_DIR / "fixtures" / "py"


def sanitized_version(output: str) -> str:
    """Replace the current marimo version with 0.0.0 for stable comparison."""
    return output.replace(__version__, "0.0.0")


def roundtrip(py_path: pathlib.Path) -> str:
    """Load a .py marimo file, export to ipynb, re-import, and return .py."""
    app = load_app(py_path)
    assert app
    internal_app = InternalApp(app)
    ipynb_str = convert_from_ir_to_ipynb(internal_app, sort_mode="top-down")
    ir = convert_from_ipynb_to_notebook_ir(ipynb_str)
    return sanitized_version(MarimoConvert.from_ir(ir).to_py())


def assert_roundtrip(fixture_name: str) -> None:
    """Assert that a fixture file survives a py -> ipynb -> py round-trip."""
    py_path = FIXTURES_PY / fixture_name
    assert py_path.exists(), f"Fixture not found: {py_path}"
    expected = py_path.read_text()
    actual = roundtrip(py_path)
    assert expected == actual


# --- Parametrized test over all fixtures ---


PY_FIXTURES = sorted(FIXTURES_PY.glob("*.py"))


@pytest.mark.parametrize(
    "py_path", PY_FIXTURES, ids=[p.stem for p in PY_FIXTURES]
)
def test_ipynb_idempotent(py_path: pathlib.Path) -> None:
    expected = py_path.read_text()
    actual = roundtrip(py_path)
    assert expected == actual


# --- Individual focused tests ---


class TestCellNamesAndDefs:
    """Cell names, @app.function, and @app.class_definition should
    survive round-trip."""

    def test_roundtrip(self) -> None:
        assert_roundtrip("cell_names_and_defs.py")

    def test_named_cells_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "cell_names_and_defs.py")
        assert "def my_imports():" in result
        assert "def compute(os, sys):" in result
        assert "def display(result):" in result

    def test_function_decorators_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "cell_names_and_defs.py")
        assert "@app.function\n" in result
        assert "@app.function(hide_code=True)" in result
        assert "@app.class_definition\n" in result
        assert "@app.class_definition(hide_code=True)" in result

    def test_function_and_class_names_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "cell_names_and_defs.py")
        assert "def add(a, b):" in result
        assert "def subtract(a, b):" in result
        assert "class MyClass:" in result
        assert "class HiddenClass:" in result


class TestSetupCell:
    """with app.setup: block should survive round-trip."""

    def test_roundtrip(self) -> None:
        assert_roundtrip("setup_cell.py")

    def test_setup_block_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "setup_cell.py")
        assert "with app.setup:" in result
        lines = result.split("\n")
        for i, line in enumerate(lines):
            if "import marimo as mo" in line and i > 0:
                prev_lines = [line for line in lines[:i] if line.strip()]
                assert prev_lines[-1].strip() == "with app.setup:"
                break


class TestCellConfig:
    """Cell configuration (hide_code, disabled) should survive round-trip."""

    def test_roundtrip(self) -> None:
        assert_roundtrip("cell_config.py")

    def test_hide_code_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "cell_config.py")
        assert "@app.cell(hide_code=True)" in result

    def test_disabled_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "cell_config.py")
        assert "@app.cell(disabled=True)" in result


class TestMarkdownStringPrefix:
    """String prefix on mo.md() calls should survive round-trip."""

    def test_roundtrip(self) -> None:
        assert_roundtrip("markdown_variants.py")

    def test_no_prefix_does_not_gain_r(self) -> None:
        """mo.md(triple-quote) without r should not gain r prefix."""
        result = roundtrip(FIXTURES_PY / "markdown_variants.py")
        assert 'mo.md("""\n    # No prefix' in result

    def test_r_prefix_preserved(self) -> None:
        result = roundtrip(FIXTURES_PY / "markdown_variants.py")
        assert 'mo.md(r"""\n    # R-prefix' in result

    def test_f_prefix_preserved(self) -> None:
        """mo.md(f-triple-quote) with no interpolation should keep f prefix."""
        result = roundtrip(FIXTURES_PY / "markdown_variants.py")
        assert 'mo.md(f"""\n    # F-prefix' in result

    def test_fr_prefix_preserved(self) -> None:
        """mo.md(fr-triple-quote) with no interpolation should keep fr prefix."""
        result = roundtrip(FIXTURES_PY / "markdown_variants.py")
        assert 'mo.md(fr"""\n    # FR-prefix' in result

    def test_f_with_interpolation_survives(self) -> None:
        """mo.md(f"...{var}...") stays as code cell, not extracted as markdown."""
        result = roundtrip(FIXTURES_PY / "markdown_variants.py")
        assert 'mo.md(f"The value is **{x}**")' in result


class TestNotebookMetadata:
    """App config and PEP 723 header should survive round-trip."""

    def test_roundtrip(self) -> None:
        assert_roundtrip("notebook_metadata.py")

    def test_app_config_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "notebook_metadata.py")
        assert 'width="medium"' in result
        assert 'auto_download=["html"]' in result

    def test_pep723_header_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "notebook_metadata.py")
        assert "# /// script" in result
        assert 'requires-python = ">=3.12"' in result
        assert '"numpy"' in result


class TestGeneratedWithVersion:
    """__generated_with should use the converting marimo version."""

    def test_roundtrip(self) -> None:
        assert_roundtrip("simple.py")

    def test_version_string_in_output(self) -> None:
        """Conversion uses the current marimo version, not the original."""
        app = load_app(FIXTURES_PY / "simple.py")
        assert app
        internal_app = InternalApp(app)
        ipynb_str = convert_from_ir_to_ipynb(
            internal_app, sort_mode="top-down"
        )
        ir = convert_from_ipynb_to_notebook_ir(ipynb_str)
        result = MarimoConvert.from_ir(ir).to_py()
        assert f'__generated_with = "{__version__}"' in result


class TestComplexFixtures:
    """Integration tests with complex fixtures combining multiple features."""

    def test_complex_file_format(self) -> None:
        assert_roundtrip("complex_file_format.py")

    def test_complex_outputs(self) -> None:
        assert_roundtrip("complex_outputs.py")
