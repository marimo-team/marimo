# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


@pytest.mark.parametrize("optimization", ["-O", "-OO"])
def test_validation_with_optimization(optimization: str) -> None:
    code = textwrap.dedent(
        """
        import pytest

        from marimo._output.show_code import show_code
        from marimo._pyodide.restartable_task import RestartableTask
        from marimo._session.requests import UpdateUIElementValuesRequest
        from marimo._utils.data_uri import from_data_uri

        with pytest.raises(ValueError, match="position must be"):
            show_code(position="invalid")

        with pytest.raises(ValueError, match="Mismatched object_ids"):
            UpdateUIElementValuesRequest(object_ids=[], values=[1])

        with pytest.raises(TypeError, match="data must be a string"):
            from_data_uri(123)

        with pytest.raises(RuntimeError, match="Task has not been started"):
            RestartableTask(lambda: None).restart()
        """
    )
    subprocess.run(
        [sys.executable, optimization, "-c", code],
        cwd=Path(__file__).resolve().parents[2],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
