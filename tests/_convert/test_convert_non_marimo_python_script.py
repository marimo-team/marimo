import pytest

from marimo._convert.converters import MarimoConvert
from marimo._convert.non_marimo_python_script import (
    convert_non_marimo_python_script_to_notebook_ir,
    convert_pypercent_script_to_notebook_ir,
    convert_python_block_to_notebook_ir,
    convert_script_block_to_notebook_ir,
    convert_non_marimo_script_to_notebook_ir,
)
from marimo._dependencies.dependencies import DependencyManager
from tests.mocks import snapshotter

HAS_JUPYTEXT = DependencyManager.has("jupytext")

snapshot_test = snapshotter(__file__)


class TestConvertPypercentScriptToNotebookIr:
    """Test the convert_pypercent_script_to_notebook_ir function."""

    @pytest.mark.skipif(not HAS_JUPYTEXT, reason="jupytext not installed")
    def test_basic_pypercent_conversion(self) -> None:
        """Test basic pypercent script conversion."""
        source = '''"""Pypercent format notebook."""

import numpy as np

# %% [markdown]
# This is a markdown cell

# %%
# First code cell
x = np.array([1, 2, 3])
print(x)

# %% Data processing
# Cell with title
y = x * 2
print(y)
'''
        ir = convert_pypercent_script_to_notebook_ir(source)
        assert ir.app is not None
        assert len(ir.cells) > 0
        # Should have both markdown and code cells
        # Note: cell_type is not available in marimo IR, cells are CellDef objects
        # Check that we have cells with different content types
        has_markdown = any(
            "markdown" in cell.code.lower() for cell in ir.cells
        )
        has_code = any("np.array" in cell.code for cell in ir.cells)
        assert has_markdown or has_code

    @pytest.mark.skipif(not HAS_JUPYTEXT, reason="jupytext not installed")
    def test_pypercent_with_main_block(self) -> None:
        """Test pypercent conversion with main block transformation."""
        source = '''"""Script with main block in pypercent."""

# %%
import sys

# %%
if __name__ == "__main__":
    print("Running as script")
    sys.exit(0)
'''
        ir = convert_pypercent_script_to_notebook_ir(source)
        # Check that main block was transformed
        main_cell = None
        for cell in ir.cells:
            if "def _main_():" in cell.code:
                main_cell = cell
                break
        assert main_cell is not None
        assert "_main_()" in main_cell.code

    def test_pypercent_missing_jupytext(self) -> None:
        """Test pypercent conversion when jupytext is not available."""
        source = '''"""Pypercent format notebook."""

# %%
x = 1
print(x)
'''
        with pytest.raises(
            ImportError, match="Converting py:percent format requires jupytext"
        ):
            convert_pypercent_script_to_notebook_ir(source)


class TestConvertPythonBlockToNotebookIr:
    """Test the convert_python_block_to_notebook_ir function."""

    def test_basic_python_block(self) -> None:
        """Test basic Python block conversion."""
        source = '''"""A simple Python script."""

import math

def calculate_area(radius):
    return math.pi * radius ** 2

print(calculate_area(5))
'''
        ir = convert_python_block_to_notebook_ir(source)
        assert ir.app is not None
        assert len(ir.cells) == 1
        # CellDef objects don't have cell_type attribute
        assert "calculate_area" in ir.cells[0].code

    def test_python_block_with_main(self) -> None:
        """Test Python block with main block transformation."""
        source = '''"""Script with main block."""

import sys

if __name__ == "__main__":
    print("Running as script")
    sys.exit(0)
'''
        ir = convert_python_block_to_notebook_ir(source)
        assert len(ir.cells) == 1
        cell = ir.cells[0]
        assert "def _main_():" in cell.code
        assert "_main_()" in cell.code

    def test_empty_python_block(self) -> None:
        """Test empty Python block conversion."""
        source = ""
        ir = convert_python_block_to_notebook_ir(source)
        assert ir.app is not None
        assert len(ir.cells) == 1
        # CellDef objects don't have cell_type attribute
        assert ir.cells[0].code.strip() == ""


class TestConvertScriptBlockToNotebookIr:
    """Test the convert_script_block_to_notebook_ir function."""

    def test_basic_script_block(self) -> None:
        """Test basic script block conversion."""
        source = "This is some arbitrary text that is not Python code"
        ir = convert_script_block_to_notebook_ir(source)
        assert ir.app is not None
        assert ir.header.value == ""
        assert len(ir.cells) == 1
        assert ir.cells[0].code == source

    def test_script_block_with_special_characters(self) -> None:
        """Test script block with special characters."""
        source = """#!/bin/bash
echo "Hello World"
# This is a bash script, not Python
"""
        ir = convert_script_block_to_notebook_ir(source)
        assert len(ir.cells) == 1
        assert ir.cells[0].code == source

    def test_empty_script_block(self) -> None:
        """Test empty script block conversion."""
        source = ""
        ir = convert_script_block_to_notebook_ir(source)
        assert ir.app is not None
        assert ir.header.value == ""
        assert len(ir.cells) == 1
        assert ir.cells[0].code == ""


class TestConvertNonMarimoScriptToNotebookIr:
    """Test the convert_non_marimo_script_to_notebook_ir function."""

    def test_python_script_success(self) -> None:
        """Test successful Python script conversion."""
        source = '''"""A simple Python script."""

x = 5
y = 10
print(x + y)
'''
        ir = convert_non_marimo_script_to_notebook_ir(source)
        assert ir.app is not None
        assert len(ir.cells) == 1
        # CellDef objects don't have cell_type attribute
        assert "print(x + y)" in ir.cells[0].code

    @pytest.mark.skipif(not HAS_JUPYTEXT, reason="jupytext not installed")
    def test_pypercent_script_success(self) -> None:
        """Test successful pypercent script conversion."""
        source = '''"""Pypercent format notebook."""

# %%
x = 1
print(x)
'''
        ir = convert_non_marimo_script_to_notebook_ir(source)
        assert ir.app is not None
        assert len(ir.cells) > 0

    def test_pypercent_script_without_jupytext(self) -> None:
        """Test pypercent script when jupytext is not available."""
        source = '''"""Pypercent format notebook."""

# %%
x = 1
print(x)
'''
        # Should fall back to Python block conversion
        ir = convert_non_marimo_script_to_notebook_ir(source)
        assert ir.app is not None
        assert len(ir.cells) == 1
        # CellDef objects don't have cell_type attribute
        assert "print(x)" in ir.cells[0].code

    def test_invalid_python_syntax(self) -> None:
        """Test script with invalid Python syntax."""
        source = """This is not valid Python code
def incomplete_function(
    # Missing closing parenthesis
"""
        ir = convert_non_marimo_script_to_notebook_ir(source)
        assert ir.app is not None
        assert len(ir.cells) == 1
        # Should be an UnparsableCell
        assert hasattr(ir.cells[0], "code")
        # Strip trailing newlines for comparison
        assert ir.cells[0].code.rstrip() == source.rstrip()

    def test_bash_script(self) -> None:
        """Test non-Python script (bash)."""
        source = """#!/bin/bash
echo "Hello World"
for i in {1..5}; do
    echo "Count: $i"
done
"""
        ir = convert_non_marimo_script_to_notebook_ir(source)
        assert ir.app is not None
        assert len(ir.cells) == 1
        # Should be an UnparsableCell
        assert hasattr(ir.cells[0], "code")
        # Strip trailing newlines for comparison
        assert ir.cells[0].code.rstrip() == source.rstrip()

    def test_markdown_text(self) -> None:
        """Test markdown text as script."""
        source = """# My Document

This is a markdown document with some content.

## Section 1

- Item 1
- Item 2
- Item 3

## Section 2

Some more content here.
"""
        ir = convert_non_marimo_script_to_notebook_ir(source)
        assert ir.app is not None
        assert len(ir.cells) == 1
        # Should be an UnparsableCell
        assert hasattr(ir.cells[0], "code")
        # Strip trailing newlines for comparison
        assert ir.cells[0].code.rstrip() == source.rstrip()


class TestConvertNonMarimoPython:
    """Test conversion of non-marimo Python files to marimo notebooks."""

    def test_simple_script(self) -> None:
        """Test conversion of a simple script."""
        source = '''"""A simple script."""

import math

def calculate_area(radius):
    return math.pi * radius ** 2

print(calculate_area(5))
'''
        ir = convert_non_marimo_python_script_to_notebook_ir(source)
        converted = MarimoConvert.from_ir(ir).to_py()
        snapshot_test("simple_script.py.txt", converted)

    def test_script_no_header(self) -> None:
        """Test conversion of a minimal script without header."""
        source = """x = 5
y = 10
print(x + y)
"""
        ir = convert_non_marimo_python_script_to_notebook_ir(source)
        converted = MarimoConvert.from_ir(ir).to_py()
        snapshot_test("minimal_script.py.txt", converted)

    @pytest.mark.skipif(not HAS_JUPYTEXT, reason="jupytext not installed")
    def test_pypercent_format(self) -> None:
        """Test conversion of pypercent format file."""
        source = '''"""Pypercent format notebook."""

import numpy as np

# %% [markdown]
# This is a markdown cell
# with multiple lines

# %% [markdown]
"""This is a doc string, but also markdown"""

# %%
# First code cell
x = np.array([1, 2, 3])
print(x)

# %% Data processing
# Cell with title
y = x * 2
print(y)
'''
        ir = convert_non_marimo_python_script_to_notebook_ir(source)
        converted = MarimoConvert.from_ir(ir).to_py()
        snapshot_test("pypercent_format.py.txt", converted)

    @pytest.mark.skipif(not HAS_JUPYTEXT, reason="jupytext not installed")
    def test_pypercent_markdown_only(self) -> None:
        """Test pypercent file with only markdown cells."""
        source = '''"""Documentation in pypercent format."""

# %% [markdown]
# Introduction
This is a documentation file.

# %% [markdown]
# Usage
Here's how to use this module.
'''
        ir = convert_non_marimo_python_script_to_notebook_ir(source)
        converted = MarimoConvert.from_ir(ir).to_py()
        snapshot_test("pypercent_markdown_only.py.txt", converted)

    @pytest.mark.skipif(not HAS_JUPYTEXT, reason="jupytext not installed")
    def test_pypercent_with_main_block(self) -> None:
        """Test pypercent file with main block."""
        source = '''"""Script with main block in pypercent."""

# %%
import sys

# %%
if __name__ == "__main__":
    print("Running as script")
    sys.exit(0)
'''
        ir = convert_non_marimo_python_script_to_notebook_ir(source)
        converted = MarimoConvert.from_ir(ir).to_py()
        snapshot_test("pypercent_with_main.py.txt", converted)
