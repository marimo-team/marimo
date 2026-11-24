# Copyright 2026 Marimo. All rights reserved.
"""Load and save scaling on large generated notebooks.

Work is measured in Python function calls, not seconds, so the bounds hold
on a loaded machine. Run with `-s` to print the measurements.
"""

from __future__ import annotations

import copy
import cProfile
import math
import pstats
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

import pytest

from marimo._session.notebook import AppFileManager
from scripts.benchmarks.generate_large_notebook import generate

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from scripts.benchmarks.generate_large_notebook import Shape

T = TypeVar("T")

SMALL = 40
LARGE = 4 * SMALL
# 1 is linear and 2 is quadratic; the slack absorbs per-notebook fixed costs.
MAX_EXPONENT = 1.5


@dataclass(frozen=True)
class Work:
    load: int
    save: int


def _calls(run: Callable[[], T]) -> tuple[T, int]:
    profiler = cProfile.Profile()
    result = profiler.runcall(run)
    return result, pstats.Stats(profiler).total_calls  # type: ignore[attr-defined]


def _measure(shape: Shape, cells: int, directory: Path) -> Work:
    path = directory / f"{shape}_{cells}.py"
    path.write_text(generate(cells, shape), encoding="utf-8")

    manager, load = _calls(lambda: AppFileManager(path))
    document = manager.app.cell_manager.document
    # The generator adds a setup cell.
    assert len(document) == cells + 1

    edited = copy.deepcopy(document.cells)
    edited[cells // 2].code += "\n# edited"
    _, save = _calls(lambda: manager.save_from_cells(edited))

    reloaded = AppFileManager(path).app.cell_manager
    assert list(reloaded.codes()) == [cell.code for cell in edited]
    assert list(reloaded.names()) == [cell.name for cell in edited]
    return Work(load=load, save=save)


def _exponent(small: int, large: int) -> float:
    return math.log(large / small) / math.log(LARGE / SMALL)


@pytest.mark.parametrize("shape", ["smoke", "chain"])
def test_load_and_save_scale_with_cell_count(
    shape: Shape, tmp_path: Path
) -> None:
    small = _measure(shape, SMALL, tmp_path)
    large = _measure(shape, LARGE, tmp_path)

    load = _exponent(small.load, large.load)
    save = _exponent(small.save, large.save)
    print(
        f"\n{shape}: load {small.load} -> {large.load} calls (n^{load:.2f}), "
        f"save {small.save} -> {large.save} calls (n^{save:.2f})"
    )
    assert load < MAX_EXPONENT
    assert save < MAX_EXPONENT
