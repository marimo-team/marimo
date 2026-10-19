# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(
    shutil.which("basedpyright") is None,
    reason="basedpyright not installed",
)


@pytest.mark.parametrize("decorator", ["memoize_last_value", "timer"])
def test_decorator_preserves_signature(decorator: str, tmp_path: Path) -> None:
    module = "memoize" if decorator == "memoize_last_value" else "timer"
    source = tmp_path / "check.py"
    source.write_text(
        textwrap.dedent(f"""
            # pyright: strict, reportUnnecessaryTypeIgnoreComment=true
            from typing_extensions import assert_type
            from marimo._utils.{module} import {decorator}

            @{decorator}
            def render(value: int, /, *, prefix: str = "") -> str:
                return prefix + str(value)

            assert_type(render(1), str)
            assert_type(render(1, prefix="value: "), str)
            render("bad")  # pyright: ignore[reportArgumentType]
            render(1, prefix=2)  # pyright: ignore[reportArgumentType]
            render(value=1)  # pyright: ignore[reportCallIssue]
            render(1, "bad")  # pyright: ignore[reportCallIssue]
            render()  # pyright: ignore[reportCallIssue]

            class Renderer:
                @{decorator}
                def render(self, value: int) -> str:
                    return str(value)

            assert_type(Renderer().render(1), str)
            Renderer().render("bad")  # pyright: ignore[reportArgumentType]
        """),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "basedpyright",
            "--pythonpath",
            sys.executable,
            "--level",
            "error",
            str(source),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
