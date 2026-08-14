# Copyright 2026 Marimo. All rights reserved.
"""Benchmarks for cell compilation and static analysis.

`compile_cell` runs every time a cell is registered and on every notebook
load, so it sits squarely on marimo's hot path.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from benchmarks.notebooks import generate_cell_codes
from marimo._ast.compiler import compile_cell
from marimo._ast.visitor import ScopedVisitor

if TYPE_CHECKING:
    from pytest_codspeed import BenchmarkFixture

SIMPLE_CELL = """\
x = 1
y = x + 1
z = [y * i for i in range(10)]
"""

COMPLEX_CELL = """\
import dataclasses
from typing import Any


@dataclasses.dataclass
class Config:
    name: str
    values: dict[str, Any]

    def merged(self, other: "Config") -> "Config":
        return Config(self.name, {**self.values, **other.values})


def build(rows, *, key=None, reverse=False):
    grouped: dict[str, list[Any]] = {}
    for row in rows:
        grouped.setdefault(row["kind"], []).append(row)
    for kind, group in grouped.items():
        group.sort(key=key, reverse=reverse)
    return grouped


async def fetch(session, urls):
    results = []
    for url in urls:
        async with session.get(url) as response:
            results.append(await response.json())
    return results


config = Config("bench", {"a": 1, "b": 2})
grouped = build([{"kind": "a", "v": i} for i in range(100)])
"""


def test_compile_cell_simple(benchmark: BenchmarkFixture) -> None:
    benchmark(compile_cell, SIMPLE_CELL, cell_id="0")


def test_compile_cell_complex(benchmark: BenchmarkFixture) -> None:
    benchmark(compile_cell, COMPLEX_CELL, cell_id="0")


def test_compile_notebook_cells(benchmark: BenchmarkFixture) -> None:
    """Compile every cell of a 50-cell notebook, as done on notebook load."""
    codes = generate_cell_codes(50)

    @benchmark
    def _() -> None:
        for index, code in enumerate(codes):
            compile_cell(code, cell_id=str(index))


def test_scoped_visitor(benchmark: BenchmarkFixture) -> None:
    """Ref/def extraction, the core of marimo's reactivity."""
    tree = ast.parse(COMPLEX_CELL)

    @benchmark
    def _() -> None:
        ScopedVisitor("bench").visit(tree)


def test_scoped_visitor_notebook(benchmark: BenchmarkFixture) -> None:
    """Ref/def extraction across every cell of a 50-cell notebook."""
    trees = [ast.parse(code) for code in generate_cell_codes(50)]

    @benchmark
    def _() -> None:
        for tree in trees:
            ScopedVisitor("bench").visit(tree)
