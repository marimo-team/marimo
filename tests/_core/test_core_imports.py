# Copyright 2026 Marimo. All rights reserved.
"""`marimo._core` imports nothing from the rest of marimo."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK = REPO_ROOT / "scripts" / "check_core_imports.py"


def run_check(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_static_check_allows_core_and_external_imports(tmp_path: Path) -> None:
    module = tmp_path / "allowed.py"
    module.write_text(
        "import dataclasses\n"
        "import msgspec\n"
        "import marimo._core.protocol\n"
        "from marimo._core import protocol\n"
    )
    result = run_check(str(module))
    assert result.returncode == 0, result.stderr


def test_static_check_sees_through_functions_and_type_checking(
    tmp_path: Path,
) -> None:
    module = tmp_path / "leaky.py"
    module.write_text(
        "from typing import TYPE_CHECKING\n"
        "from marimo._core import protocol\n"
        "if TYPE_CHECKING:\n"
        "    from marimo._types.ids import NotebookId\n"
        "def later():\n"
        "    import marimo._utils.code\n"
        "    from marimo import _loggers\n"
    )
    result = run_check(str(module))
    assert result.returncode == 1
    assert "leaky.py:4: imports marimo._types.ids" in result.stderr
    assert "leaky.py:6: imports marimo._utils.code" in result.stderr
    assert "leaky.py:7: imports marimo" in result.stderr
