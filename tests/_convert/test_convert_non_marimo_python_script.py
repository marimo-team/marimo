import pytest

from marimo._convert.converters import MarimoConvert
from marimo._convert.non_marimo_python_script import (
    convert_non_marimo_python_script_to_notebook_ir,
)
from marimo._dependencies.dependencies import DependencyManager
from tests.mocks import snapshotter

HAS_JUPYTEXT = DependencyManager.has("jupytext")

snapshot_test = snapshotter(__file__)


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
