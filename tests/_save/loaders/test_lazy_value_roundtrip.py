# Copyright 2026 Marimo. All rights reserved.
"""Values survive a lazy-loader save and restore with their type and value."""

from __future__ import annotations

import enum
import subprocess
import sys
from typing import TYPE_CHECKING, Any

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._save.cache import Cache
from marimo._save.loaders import LazyLoader
from marimo._save.stores.file import FileStore

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

HAS_NUMPY = DependencyManager.numpy.has()
HAS_PANDAS_ARROW = (
    DependencyManager.pandas.has() and DependencyManager.pyarrow.has()
)


class Color(enum.IntEnum):
    RED = 1


class Mode(str, enum.Enum):
    A = "a"


class Tag(str):
    pass


def _round_trip(value: Any, tmp_path: Path) -> Any:
    cache = Cache(
        defs={"v": value},
        hash="roundtrip",
        cache_type="Pure",
        stateful_refs=set(),
        hit=False,
        meta={},
    )
    cache.update({"v": value})
    loader = LazyLoader("test", store=FileStore(save_path=str(tmp_path)))
    assert loader.save_cache(cache)
    loader.flush()
    loaded = loader.load_cache(cache.key)
    assert loaded is not None
    scope: dict[str, Any] = {"__name__": "__main__"}
    loaded.restore(scope)
    return scope["v"]


@pytest.mark.parametrize(
    "value",
    [Color.RED, Mode.A, Tag("q")],
    ids=["int-enum", "str-enum", "str-subclass"],
)
def test_builtin_subclass_keeps_type(value: Any, tmp_path: Path) -> None:
    restored = _round_trip(value, tmp_path)
    assert type(restored) is type(value)
    assert restored == value


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy required")
def test_numpy_subclasses_keep_type(tmp_path: Path) -> None:
    import numpy as np

    masked = np.ma.array([1, 2, 3], mask=[0, 0, 1])
    restored = _round_trip(masked, tmp_path)
    assert isinstance(restored, np.ma.MaskedArray)
    assert restored.mask.tolist() == [False, False, True]
    assert restored.sum() == 3

    restored_str = _round_trip(np.str_("z"), tmp_path)
    assert type(restored_str) is np.str_


@pytest.mark.skipif(not HAS_PANDAS_ARROW, reason="pandas and pyarrow required")
@pytest.mark.parametrize(
    "make",
    [
        lambda pd: pd.Series([1, 2]),
        lambda pd: pd.Series([1, 2], name=0),
        lambda pd: pd.Series(["a", "b"], dtype="string"),
        lambda pd: pd.Series(["a", "b"], dtype="category"),
        lambda pd: pd.Series(pd.date_range("2024", periods=2, tz="UTC")),
    ],
    ids=["unnamed", "named-0", "string", "category", "tz-aware"],
)
def test_pandas_series_round_trip(
    make: Callable[[Any], Any], tmp_path: Path
) -> None:
    import pandas as pd

    series = make(pd)
    pd.testing.assert_series_equal(_round_trip(series, tmp_path), series)


NOTEBOOK_SOURCE = """import marimo

app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    with mo.persistent_cache("block"):
        inc = lambda v: v + 1
    print("block", inc(1))
    return


@app.cell
def _(mo):
    @mo.persistent_cache
    def make():
        return lambda v: v + 2

    print("function", make()(1))
    return


if __name__ == "__main__":
    app.run()
"""


def test_unpicklable_value_runs_live_on_every_run(tmp_path: Path) -> None:
    """A value that cannot be pickled is recomputed rather than restored."""
    nb_path = tmp_path / "notebook.py"
    nb_path.write_text(NOTEBOOK_SOURCE, encoding="utf-8")

    for _ in range(2):
        run = subprocess.run(
            [sys.executable, str(nb_path)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            timeout=120,
        )
        assert run.returncode == 0, run.stderr
        assert "block 2" in run.stdout
        assert "function 3" in run.stdout
