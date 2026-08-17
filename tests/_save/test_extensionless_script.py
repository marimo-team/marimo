# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

NOTEBOOK_SOURCE = """import marimo

app = marimo.App()

with app.setup:
    import marimo as mo


@app.cell
def _():
    with mo.persistent_cache("extensionless"):
        print("computed")
        value = 42
    print(f"value={value}")
    return


if __name__ == "__main__":
    app.run()
"""


def test_persistent_cache_in_extensionless_script(tmp_path: Path) -> None:
    """`mo.persistent_cache` works when the notebook runs from a spool copy.

    Slurm executes sbatch scripts from an extensionless copy of the submitted
    file. The cache block must still resolve its enclosing cell.
    """
    spool_path = tmp_path / "slurm_script"
    spool_path.write_text(NOTEBOOK_SOURCE, encoding="utf-8")

    for run in range(2):
        result = subprocess.run(
            [sys.executable, str(spool_path)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            timeout=120,
        )
        assert result.returncode == 0, (run, result.stderr)
        assert "value=42" in result.stdout
        # The first run computes; the second restores from the cache, so
        # the block body must not re-execute.
        block_ran = "computed" in result.stdout
        assert block_ran == (run == 0), (run, result.stdout)

    cache_dir = tmp_path / "__marimo__" / "cache"
    assert cache_dir.is_dir()
    assert any(cache_dir.iterdir())
