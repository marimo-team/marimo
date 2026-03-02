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
FIXTURES_PY = SELF_DIR / "fixtures" / "py"


def roundtrip(py_path: pathlib.Path) -> str:
    """Load a .py marimo file, export to ipynb, re-import, and return .py."""
    app = load_app(py_path)
    assert app
    internal_app = InternalApp(app)
    ipynb_str = convert_from_ir_to_ipynb(internal_app, sort_mode="top-down")
    ir = convert_from_ipynb_to_notebook_ir(ipynb_str)
    return MarimoConvert.from_ir(ir).to_py()


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


class TestCellNames:
    """Cell names stored in ipynb metadata should survive round-trip."""

    def test_named_cells_preserved(self) -> None:
        assert_roundtrip("cell_names.py")

    def test_named_cells_in_output(self) -> None:
        """Verify named function defs appear in the round-tripped output."""
        result = roundtrip(FIXTURES_PY / "cell_names.py")
        assert "def my_imports():" in result
        assert "def compute(os, sys):" in result


class TestSetupCell:
    """with app.setup: block should survive round-trip."""

    def test_setup_block_preserved(self) -> None:
        assert_roundtrip("setup_cell.py")

    def test_setup_block_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "setup_cell.py")
        assert "with app.setup:" in result
        # Should NOT become a regular @app.cell
        lines = result.split("\n")
        # Find the import marimo as mo line - it should be under setup, not a cell
        for i, line in enumerate(lines):
            if "import marimo as mo" in line and i > 0:
                # The preceding non-empty line should be the setup block
                prev_lines = [
                    l for l in lines[:i] if l.strip()
                ]
                assert prev_lines[-1].strip() == "with app.setup:"
                break


class TestCellConfig:
    """Cell configuration (hide_code, disabled) should survive round-trip."""

    def test_hide_code_preserved(self) -> None:
        assert_roundtrip("hide_code.py")

    def test_hide_code_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "hide_code.py")
        assert "@app.cell(hide_code=True)" in result

    def test_disabled_preserved(self) -> None:
        assert_roundtrip("disabled_cell.py")

    def test_disabled_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "disabled_cell.py")
        assert "@app.cell(disabled=True)" in result


class TestMarkdownStringPrefix:
    """String prefix on mo.md() calls should survive round-trip."""

    def test_no_r_prefix(self) -> None:
        """mo.md(triple-quote) without r should not gain r prefix."""
        assert_roundtrip("markdown_no_r.py")

    def test_no_r_prefix_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "markdown_no_r.py")
        assert 'mo.md("""' in result
        assert 'mo.md(r"""' not in result

    def test_r_prefix(self) -> None:
        """mo.md(r-triple-quote) should preserve r prefix."""
        assert_roundtrip("markdown_r.py")

    def test_r_prefix_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "markdown_r.py")
        assert 'mo.md(r"""' in result

    def test_f_prefix_no_interpolation(self) -> None:
        """mo.md(f-triple-quote) with no interpolation should preserve f prefix."""
        assert_roundtrip("markdown_f.py")

    def test_f_prefix_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "markdown_f.py")
        assert 'mo.md(f"""' in result
        assert 'mo.md(r"""' not in result

    def test_fr_prefix_no_interpolation(self) -> None:
        """mo.md(fr-triple-quote) with no interpolation should preserve fr prefix."""
        assert_roundtrip("markdown_fr.py")

    def test_fr_prefix_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "markdown_fr.py")
        assert 'mo.md(fr"""' in result

    def test_f_with_interpolation(self) -> None:
        """mo.md(f"...{var}...") should stay as code cell and survive."""
        assert_roundtrip("markdown_f_interp.py")

    def test_f_with_interpolation_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "markdown_f_interp.py")
        assert 'mo.md(f"The value is **{x}**")' in result


class TestAppConfig:
    """App configuration should survive round-trip."""

    def test_app_config_preserved(self) -> None:
        assert_roundtrip("app_config.py")

    def test_app_config_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "app_config.py")
        assert 'width="medium"' in result
        assert 'auto_download=["html"]' in result


class TestPEP723Header:
    """PEP 723 script metadata should survive round-trip."""

    def test_header_preserved(self) -> None:
        assert_roundtrip("pep723_header.py")

    def test_header_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "pep723_header.py")
        assert "# /// script" in result
        assert 'requires-python = ">=3.12"' in result
        assert '"numpy"' in result


class TestFunctionAndClass:
    """@app.function and @app.class_definition should survive round-trip."""

    def test_function_and_class_preserved(self) -> None:
        assert_roundtrip("function_and_class.py")

    def test_decorators_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "function_and_class.py")
        assert "@app.function\n" in result
        assert "@app.function(hide_code=True)" in result
        assert "@app.class_definition\n" in result
        assert "@app.class_definition(hide_code=True)" in result

    def test_function_names_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "function_and_class.py")
        assert "def add(a, b):" in result
        assert "def subtract(a, b):" in result
        assert "class MyClass:" in result
        assert "class HiddenClass:" in result


class TestGeneratedWithVersion:
    """__generated_with version should be preserved, not replaced."""

    def test_version_preserved(self) -> None:
        assert_roundtrip("simple.py")

    def test_version_string_in_output(self) -> None:
        result = roundtrip(FIXTURES_PY / "simple.py")
        assert '__generated_with = "0.19.2"' in result


class TestComplexFixtures:
    """Integration tests with complex fixtures combining multiple features."""

    def test_complex_file_format(self) -> None:
        assert_roundtrip("complex_file_format.py")

    def test_complex_outputs(self) -> None:
        assert_roundtrip("complex_outputs.py")
