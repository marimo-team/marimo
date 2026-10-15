# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

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
