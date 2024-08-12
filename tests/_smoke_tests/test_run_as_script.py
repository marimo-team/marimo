from __future__ import annotations

import inspect
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from marimo._dependencies.dependencies import DependencyManager

if TYPE_CHECKING:
    import pathlib


class TestRunTutorialsAsScripts:
    def assert_not_errored(
        self, p: subprocess.CompletedProcess[bytes]
    ) -> None:
        assert p.returncode == 0
        assert not any(
            line.startswith("Traceback")
            for line in p.stderr.decode().splitlines()
        )
        assert not any(
            line.startswith("Traceback")
            for line in p.stdout.decode().splitlines()
        )

    def assert_errored(
        self, p: subprocess.CompletedProcess[bytes], reason: str
    ) -> None:
        assert p.returncode != 0
        assert reason in p.stderr.decode()

    @pytest.mark.skipif(
        condition=sys.platform == "win32", reason="Encoding error"
    )
    def test_run_intro_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import intro

        file = tmp_path / "intro.py"
        file.write_text(inspect.getsource(intro))
        p = subprocess.run(
            ["python", str(file)],
            capture_output=True,
        )
        self.assert_not_errored(p)

    @pytest.mark.skipif(
        condition=sys.platform == "win32", reason="Encoding error"
    )
    def test_run_ui_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import ui as mod

        file = tmp_path / "mod.py"
        file.write_text(inspect.getsource(mod))
        p = subprocess.run(
            ["python", str(file)],
            capture_output=True,
        )
        self.assert_not_errored(p)

    @pytest.mark.skipif(
        condition=sys.platform == "win32", reason="Encoding error"
    )
    def test_run_dataflow_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import dataflow as mod

        file = tmp_path / "mod.py"
        file.write_text(inspect.getsource(mod))
        p = subprocess.run(
            ["python", str(file)],
            capture_output=True,
        )
        self.assert_errored(p, reason="CycleError")

    @pytest.mark.skipif(
        condition=sys.platform == "win32", reason="Encoding error"
    )
    def test_run_layout_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import layout as mod

        file = tmp_path / "mod.py"
        file.write_text(inspect.getsource(mod))
        p = subprocess.run(
            ["python", str(file)],
            capture_output=True,
        )
        self.assert_not_errored(p)

    @pytest.mark.skipif(
        condition=not DependencyManager.matplotlib.has(),
        reason="requires matplotlib",
    )
    @pytest.mark.skipif(
        condition=sys.platform == "win32", reason="Encoding error"
    )
    def test_run_plots_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import plots as mod

        file = tmp_path / "mod.py"
        file.write_text(inspect.getsource(mod))
        p = subprocess.run(
            ["python", str(file)],
            capture_output=True,
        )
        self.assert_not_errored(p)

    @pytest.mark.skipif(
        condition=sys.platform == "win32", reason="Encoding error"
    )
    def test_run_marimo_for_jupyter_users_tutorial(
        self, tmp_path: pathlib.Path
    ) -> None:
        from marimo._tutorials import for_jupyter_users as mod

        file = tmp_path / "mod.py"
        file.write_text(inspect.getsource(mod))
        p = subprocess.run(
            ["python", str(file)],
            capture_output=True,
        )
        self.assert_errored(p, reason="MultipleDefinitionError")

    @pytest.mark.skipif(
        condition=sys.platform == "win32", reason="Encoding error"
    )
    def test_run_disabled_cells(self, tmp_path: pathlib.Path) -> None:
        code = """
import marimo

app = marimo.App()

@app.cell
def enabled_cell():
    print("enabled cell")

@app.cell(disabled=True)
def disabled_cell():
    print("disabled cell")

if __name__ == "__main__":
    app.run()
        """
        file = tmp_path / "mod.py"
        file.write_text(code)
        p = subprocess.run(
            ["python", str(file)],
            capture_output=True,
        )
        self.assert_not_errored(p)
        assert "enabled cell" in p.stdout.decode()
        assert "disabled cell" not in p.stdout.decode()
