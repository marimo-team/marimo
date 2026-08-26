# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("basedpyright") is None,
    reason="basedpyright not installed",
)


def _check_pyright(code: str) -> None:
    """Run basedpyright on *code* and assert zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "check.py"
        p.write_text(textwrap.dedent(code))
        result = subprocess.run(
            [
                "basedpyright",
                "--pythonpath",
                sys.executable,
                "--level",
                "error",
                str(p),
            ],
            capture_output=True,
            text=True,
        )
    assert result.returncode == 0, (
        f"basedpyright exited with code {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


class TestDictionaryAndBatchAcceptSubclassDicts:
    """Regression tests for https://github.com/marimo-team/marimo/issues/10631

    `dict` is invariant, so a `dict[str, mo.ui.checkbox]` was previously
    rejected by static type checkers wherever `dict[str, UIElement[Any, Any]]`
    was required. The constructors now accept `Mapping`, which is covariant.
    """

    def test_dictionary_accepts_subclass_dict(self) -> None:
        _check_pyright("""
            import marimo as mo

            elements: dict[str, mo.ui.checkbox] = {
                "a": mo.ui.checkbox(),
            }
            mo.ui.dictionary(elements)
        """)

    def test_batch_accepts_subclass_dict(self) -> None:
        _check_pyright("""
            import marimo as mo

            elements: dict[str, mo.ui.checkbox] = {
                "a": mo.ui.checkbox(),
            }
            mo.ui.batch(mo.md("{a}"), elements)
        """)

    def test_validate_and_clone_accepts_subclass_dict(self) -> None:
        _check_pyright("""
            import marimo as mo
            from marimo._plugins.ui._impl.batch import validate_and_clone

            elements: dict[str, mo.ui.checkbox] = {
                "a": mo.ui.checkbox(),
            }
            validate_and_clone(elements)
        """)
