# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._save.manifest import CacheManifest, is_manifest_name

if TYPE_CHECKING:
    from pathlib import Path

NOTEBOOK_SOURCE = """# /// script
# [tool.marimo.runtime]
# cache_cells = true
# ///
import marimo

app = marimo.App()


@app.cell
def _():
    value = sum(range(1000))
    print(f"computed value={value}")
    return (value,)


@app.cell
def _(value):
    doubled = value * 2
    print(f"downstream doubled={doubled}")
    return (doubled,)


if __name__ == "__main__":
    app.run()
"""


def test_script_run_populates_and_restores_cell_cache(tmp_path: Path) -> None:
    """`python notebook.py` warms the `cache_cells` cell cache.

    The first run executes cell bodies and saves them to
    `__marimo__/cache`. The second run restores from cache, so the cell
    bodies (and their prints) do not run.
    """
    nb_path = tmp_path / "notebook.py"
    nb_path.write_text(NOTEBOOK_SOURCE, encoding="utf-8")

    first = subprocess.run(
        [sys.executable, str(nb_path)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=120,
    )
    assert first.returncode == 0, first.stderr
    assert "computed value=499500" in first.stdout
    assert "downstream doubled=999000" in first.stdout

    cache_dir = tmp_path / "__marimo__" / "cache"
    assert cache_dir.is_dir(), "script run must create the cell cache"
    assert any(cache_dir.rglob("*")), "script run must write cache entries"

    second = subprocess.run(
        [sys.executable, str(nb_path)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=120,
    )
    assert second.returncode == 0, second.stderr
    assert "computed value" not in second.stdout, (
        "cached cell body ran again instead of restoring"
    )


def test_script_run_records_its_cache_entries_in_a_manifest(
    tmp_path: Path,
) -> None:
    """A script run writes the manifest that `marimo cache` commands read."""
    nb_path = tmp_path / "notebook.py"
    nb_path.write_text(NOTEBOOK_SOURCE, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(nb_path)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr

    cache_dir = tmp_path / "__marimo__" / "cache"
    (manifest_path,) = [
        path for path in cache_dir.iterdir() if is_manifest_name(path.name)
    ]
    manifest = CacheManifest.from_bytes(manifest_path.read_bytes())
    entries = manifest.entries()
    assert len(entries) == 2, "one entry per cell"
    assert {block for block, _ in entries} == {"cell_cache"}


def test_script_run_without_cache_cells_stays_cold(tmp_path: Path) -> None:
    """Without `cache_cells`, script runs execute every cell, every time."""
    source = NOTEBOOK_SOURCE.replace("# cache_cells = true\n", "")
    nb_path = tmp_path / "notebook.py"
    nb_path.write_text(source, encoding="utf-8")

    for _ in range(2):
        result = subprocess.run(
            [sys.executable, str(nb_path)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "computed value=499500" in result.stdout

    assert not (tmp_path / "__marimo__" / "cache").exists()


# `x` is not a primitive, so the consumer's cache key hashes the code of
# the cell that defines `x` rather than its value.
OVERRIDE_NOTEBOOK_SOURCE = """# /// script
# [tool.marimo.runtime]
# cache_cells = true
# ///
import marimo

app = marimo.App()

with app.setup:
    from types import SimpleNamespace


@app.cell
def _():
    x = SimpleNamespace(value=1)
    return (x,)


@app.cell
def _(x):
    y = x.value
    print(f"computed y={y}")
    return (y,)
"""

OVERRIDE_DRIVER_SOURCE = """import sys
from types import SimpleNamespace

from notebook import app

overrides = {"x": SimpleNamespace(value=2)} if sys.argv[1:] else None
_, defs = app.run(defs=overrides)
print(f"returned y={defs['y']}")
"""


def test_app_run_with_overrides_bypasses_cell_cache(tmp_path: Path) -> None:
    """`App.run(defs=...)` neither restores nor saves cached cells."""
    (tmp_path / "notebook.py").write_text(
        OVERRIDE_NOTEBOOK_SOURCE, encoding="utf-8"
    )
    driver = tmp_path / "driver.py"
    driver.write_text(OVERRIDE_DRIVER_SOURCE, encoding="utf-8")

    def run(*args: str) -> str:
        result = subprocess.run(
            [sys.executable, str(driver), *args],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout

    assert "returned y=1" in run()
    assert "returned y=2" in run("--override")
    warm = run()
    assert "returned y=1" in warm
    assert "computed y" not in warm, "the first run's entry should restore"


ARRAY_NOTEBOOK_SOURCE = """import marimo

app = marimo.App()


@app.cell
def _():
    import numpy as np

    return (np,)


@app.cell
def _(np):
    x = np.array([1, 2])
    return (x,)


@app.cell
def _(x):
    y = int(x.sum())
    return (y,)
"""

# Both notebooks run inside this notebook's cell, so they reuse its runtime
# context, including the `cache_cells` setting.
HOST_NOTEBOOK_SOURCE = """# /// script
# [tool.marimo.runtime]
# cache_cells = true
# ///
import marimo

app = marimo.App()


@app.cell
def _():
    import ones
    import tens

    _, ones_defs = ones.app.run()
    _, tens_defs = tens.app.run()
    print(f"returned y={ones_defs['y']},{tens_defs['y']}")
    return


if __name__ == "__main__":
    app.run()
"""


@pytest.mark.skipif(
    not DependencyManager.numpy.has(), reason="numpy not installed"
)
def test_app_runs_in_one_context_hash_their_own_values(tmp_path: Path) -> None:
    """Each `App.run()` hashes its own values, even in a shared context.

    Content hashes are memoized by variable name. A second run that read
    the first run's memo would hash its `x` as `[1, 2]` and restore the
    first run's `y`.
    """
    (tmp_path / "ones.py").write_text(ARRAY_NOTEBOOK_SOURCE, encoding="utf-8")
    (tmp_path / "tens.py").write_text(
        ARRAY_NOTEBOOK_SOURCE.replace("[1, 2]", "[10, 20]"), encoding="utf-8"
    )
    host = tmp_path / "host.py"
    host.write_text(HOST_NOTEBOOK_SOURCE, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(host)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "returned y=3,30" in result.stdout
