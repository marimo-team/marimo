# Copyright 2026 Marimo. All rights reserved.
"""Benchmarks for reading and writing marimo notebook files.

`parse_notebook` is invoked whenever a notebook is opened, watched, exported
or linted; `generate_filecontents` runs on every save.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmarks.notebooks import generate_cell_codes
from marimo._ast.app_config import _AppConfig
from marimo._ast.cell import CellConfig
from marimo._ast.codegen import (
    generate_filecontents,
    generate_filecontents_from_ir,
)
from marimo._ast.parse import parse_notebook
from marimo._convert.converters import MarimoConvert

if TYPE_CHECKING:
    from pytest_codspeed import BenchmarkFixture


def test_parse_notebook_small(
    benchmark: BenchmarkFixture, small_notebook: str
) -> None:
    benchmark(parse_notebook, small_notebook, filepath="notebook.py")


def test_parse_notebook(benchmark: BenchmarkFixture, notebook: str) -> None:
    benchmark(parse_notebook, notebook, filepath="notebook.py")


def test_parse_notebook_large(
    benchmark: BenchmarkFixture, large_notebook: str
) -> None:
    benchmark(parse_notebook, large_notebook, filepath="notebook.py")


def test_generate_filecontents(benchmark: BenchmarkFixture) -> None:
    """Serialize 50 cells back to a notebook file, as done on save."""
    codes = generate_cell_codes(50)
    names = [f"cell_{i}" for i in range(len(codes))]
    configs = [CellConfig() for _ in codes]
    config = _AppConfig(width="medium")

    @benchmark
    def _() -> None:
        generate_filecontents(
            list(codes), list(names), list(configs), config=config
        )


def test_generate_filecontents_from_ir(
    benchmark: BenchmarkFixture, notebook: str
) -> None:
    ir = parse_notebook(notebook, filepath="notebook.py")
    assert ir is not None
    benchmark(generate_filecontents_from_ir, ir)


def test_notebook_roundtrip(
    benchmark: BenchmarkFixture, notebook: str
) -> None:
    """Parse a notebook and serialize it back, the full save path."""

    @benchmark
    def _() -> str:
        return MarimoConvert.from_py(notebook).to_py()
