# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import inspect
import subprocess
import sys
from os import path
from typing import TYPE_CHECKING

import pytest

from marimo import __version__
from marimo._dependencies.dependencies import DependencyManager
from tests._server.templates.utils import normalize_index_html
from tests.mocks import snapshotter

if TYPE_CHECKING:
    import pathlib

snapshot = snapshotter(__file__)


def _is_win32() -> bool:
    return sys.platform == "win32"


class TestExportHTML:
    @staticmethod
    def test_cli_export_html(temp_marimo_file: str) -> None:
        p = subprocess.run(
            ["marimo", "export", "html", temp_marimo_file],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        html = normalize_index_html(p.stdout.decode())
        # Remove folder path
        dirname = path.dirname(temp_marimo_file)
        html = html.replace(dirname, "path")
        assert '<marimo-code hidden=""></marimo-code>' not in html

    @staticmethod
    def test_cli_export_html_no_code(temp_marimo_file: str) -> None:
        p = subprocess.run(
            [
                "marimo",
                "export",
                "html",
                temp_marimo_file,
                "--no-include-code",
            ],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        html = normalize_index_html(p.stdout.decode())
        # Remove folder path
        dirname = path.dirname(temp_marimo_file)
        html = html.replace(dirname, "path")
        assert '<marimo-code hidden=""></marimo-code>' in html

    @staticmethod
    def test_cli_export_async(temp_async_marimo_file: str) -> None:
        p = subprocess.run(
            ["marimo", "export", "html", temp_async_marimo_file],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        assert "ValueError" not in p.stderr.decode()
        assert "Traceback" not in p.stderr.decode()
        html = normalize_index_html(p.stdout.decode())
        # Remove folder path
        dirname = path.dirname(temp_async_marimo_file)
        html = html.replace(dirname, "path")
        assert '<marimo-code hidden=""></marimo-code>' not in html

    @pytest.mark.skipif(
        condition=DependencyManager.watchdog.has(),
        reason="hangs when watchdog is installed",
    )
    async def test_export_watch(self, temp_marimo_file: str) -> None:
        temp_out_file = temp_marimo_file.replace(".py", ".html")
        p = subprocess.Popen(  # noqa: ASYNC101 ASYNC220
            [
                "marimo",
                "export",
                "html",
                temp_marimo_file,
                "--watch",
                "--output",
                temp_out_file,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for the message
        while True:
            line = p.stdout.readline().decode()
            if line:
                assert f"Watching {temp_marimo_file}" in line
                break

        assert not path.exists(temp_out_file)

        # Modify file
        with open(temp_marimo_file, "a") as f:  # noqa: ASYNC101 ASYNC230
            f.write("\n# comment\n")

        assert p.poll() is None
        # Wait for rebuild
        # TODO: This hangs when watchdog is installed.
        while True:
            line = p.stdout.readline().decode()
            if line:
                assert "Re-exporting" in line
                break

    @pytest.mark.skipif(
        condition=DependencyManager.watchdog.has(),
        reason="hangs when watchdog is installed",
    )
    def test_export_watch_no_out_dir(self, temp_marimo_file: str) -> None:
        p = subprocess.Popen(
            [
                "marimo",
                "export",
                "html",
                temp_marimo_file,
                "--watch",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Should return an error
        while True:
            line = p.stderr.readline().decode()
            if line:
                assert (
                    "Cannot use --watch without providing "
                    + "an output file with --output."
                    in line
                )
                break


class TestExportHtmlSmokeTests:
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

    def test_export_intro_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import intro

        file = tmp_path / "intro.py"
        out = tmp_path / "out.html"
        file.write_text(inspect.getsource(intro), encoding="utf-8")
        p = subprocess.run(
            ["marimo", "export", "html", str(file), "-o", str(out)],
            capture_output=True,
        )
        self.assert_not_errored(p)

    def test_export_ui_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import ui as mod

        file = tmp_path / "mod.py"
        file.write_text(inspect.getsource(mod), encoding="utf-8")
        out = tmp_path / "out.html"
        p = subprocess.run(
            ["marimo", "export", "html", str(file), "-o", str(out)],
            capture_output=True,
        )
        self.assert_not_errored(p)

    def test_export_dataflow_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import dataflow as mod

        file = tmp_path / "mod.py"
        file.write_text(inspect.getsource(mod), encoding="utf-8")
        out = tmp_path / "out.html"
        p = subprocess.run(
            ["marimo", "export", "html", str(file), "-o", str(out)],
            capture_output=True,
        )
        self.assert_not_errored(p)

    def test_export_layout_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import layout as mod

        file = tmp_path / "mod.py"
        file.write_text(inspect.getsource(mod), encoding="utf-8")
        out = tmp_path / "out.html"
        p = subprocess.run(
            ["marimo", "export", "html", str(file), "-o", str(out)],
            capture_output=True,
        )
        self.assert_not_errored(p)

    def test_export_plots_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import plots as mod

        file = tmp_path / "plots.py"
        file.write_text(inspect.getsource(mod), encoding="utf-8")
        out = tmp_path / "out.html"
        p = subprocess.run(
            ["marimo", "export", "html", str(file), "-o", str(out)],
            capture_output=True,
        )
        self.assert_not_errored(p)

    def test_export_marimo_for_jupyter_users(
        self, tmp_path: pathlib.Path
    ) -> None:
        from marimo._tutorials import for_jupyter_users as mod

        file = tmp_path / "mod.py"
        file.write_text(inspect.getsource(mod), encoding="utf-8")
        out = tmp_path / "out.html"
        p = subprocess.run(
            ["marimo", "export", "html", str(file), "-o", str(out)],
            capture_output=True,
        )
        self.assert_not_errored(p)


class TestExportScript:
    @staticmethod
    def test_export_script(temp_marimo_file: str) -> None:
        p = subprocess.run(
            ["marimo", "export", "script", temp_marimo_file],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        output = p.stdout.decode()
        output = output.replace(__version__, "0.0.0")
        snapshot("script.txt", output)

    @staticmethod
    def test_export_script_async(temp_async_marimo_file: str) -> None:
        p = subprocess.run(
            ["marimo", "export", "script", temp_async_marimo_file],
            capture_output=True,
        )
        assert p.returncode == 2, p.stderr.decode()
        assert (
            "Cannot export a notebook with async code to a flat script"
            in p.stderr.decode()
        )

    @pytest.mark.skipif(
        condition=DependencyManager.watchdog.has() or _is_win32(),
        reason="hangs when watchdog is installed, flaky on Windows",
    )
    async def test_export_watch_script(self, temp_marimo_file: str) -> None:
        temp_out_file = temp_marimo_file.replace(".py", ".script.py")
        p = subprocess.Popen(  # noqa: ASYNC101 ASYNC220
            [
                "marimo",
                "export",
                "script",
                temp_marimo_file,
                "--watch",
                "--output",
                temp_out_file,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for the message
        while True:
            line = p.stdout.readline().decode()
            if line:
                assert f"Watching {temp_marimo_file}" in line
                break

        assert not path.exists(temp_out_file)

        # Modify file
        with open(temp_marimo_file, "a") as f:  # noqa: ASYNC101 ASYNC230
            f.write("\n# comment\n")

        assert p.poll() is None
        # Wait for rebuild
        while True:
            line = p.stdout.readline().decode()
            if line:
                assert "Re-exporting" in line
                break

        await asyncio.sleep(0.1)
        assert path.exists(temp_out_file)

    @pytest.mark.skipif(
        condition=DependencyManager.watchdog.has(),
        reason="hangs when watchdog is installed",
    )
    def test_export_watch_script_no_out_dir(
        self, temp_marimo_file: str
    ) -> None:
        p = subprocess.Popen(
            [
                "marimo",
                "export",
                "script",
                temp_marimo_file,
                "--watch",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Should return an error
        while True:
            line = p.stderr.readline().decode()
            if line:
                assert (
                    "Cannot use --watch without providing "
                    + "an output file with --output."
                    in line
                )
                break


class TestExportMarkdown:
    @staticmethod
    def test_export_markdown(temp_marimo_file: str) -> None:
        p = subprocess.run(
            ["marimo", "export", "md", temp_marimo_file],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        output = p.stdout.decode()
        output = output.replace(__version__, "0.0.0")
        snapshot("markdown.txt", output)

    @staticmethod
    def test_export_markdown_async(temp_async_marimo_file: str) -> None:
        p = subprocess.run(
            ["marimo", "export", "md", temp_async_marimo_file],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        output = p.stdout.decode()
        output = output.replace(__version__, "0.0.0")
        snapshot("async.txt", output)

    @staticmethod
    def test_export_markdown_broken(temp_unparsable_marimo_file: str) -> None:
        p = subprocess.run(
            ["marimo", "export", "md", temp_unparsable_marimo_file],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        output = p.stdout.decode()
        output = output.replace(__version__, "0.0.0")
        snapshot("broken.txt", output)

    @pytest.mark.skipif(
        condition=DependencyManager.watchdog.has() or _is_win32(),
        reason="hangs when watchdog is installed, flaky on Windows",
    )
    async def test_export_watch_markdown(self, temp_marimo_file: str) -> None:
        temp_out_file = temp_marimo_file.replace(".py", ".md")
        p = subprocess.Popen(  # noqa: ASYNC101 ASYNC220
            [
                "marimo",
                "export",
                "md",
                temp_marimo_file,
                "--watch",
                "--output",
                temp_out_file,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for the message
        while True:
            line = p.stdout.readline().decode()
            if line:
                assert f"Watching {temp_marimo_file}" in line
                break

        assert not path.exists(temp_out_file)

        # Modify file
        with open(temp_marimo_file, "a") as f:  # noqa: ASYNC101 ASYNC230
            f.write("\n# comment\n")

        assert p.poll() is None
        # Wait for rebuild
        while True:
            line = p.stdout.readline().decode()
            if line:
                assert "Re-exporting" in line
                break

        await asyncio.sleep(0.1)
        assert path.exists(temp_out_file)

    @pytest.mark.skipif(
        condition=DependencyManager.watchdog.has(),
        reason="hangs when watchdog is installed",
    )
    def test_export_watch_markdown_no_out_dir(
        self, temp_marimo_file: str
    ) -> None:
        p = subprocess.Popen(
            [
                "marimo",
                "export",
                "md",
                temp_marimo_file,
                "--watch",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Should return an error
        while True:
            line = p.stderr.readline().decode()
            if line:
                assert (
                    "Cannot use --watch without providing "
                    + "an output file with --output."
                    in line
                )
                break


class TestExportIpynb:
    # @pytest.mark.skipif(
    #     not DependencyManager.nbformat.has(),
    #     reason="This test requires nbformat.",
    # )
    # Flaky on CI
    @pytest.mark.skip
    def test_export_ipynb(self, temp_marimo_file_with_md: str) -> None:
        p = subprocess.run(
            ["marimo", "export", "ipynb", temp_marimo_file_with_md],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        output = p.stdout.decode()
        # ipynb has non-deterministic ids
        snapshot("ipynb.txt", output)

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has(),
        reason="This test requires nbformat.",
    )
    def test_export_ipynb_sort_modes(
        self, temp_marimo_file_with_md: str
    ) -> None:
        # Test topological sort (default)
        p = subprocess.run(
            ["marimo", "export", "ipynb", temp_marimo_file_with_md],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        topo_output = p.stdout.decode()

        # Test top-down sort
        p = subprocess.run(
            [
                "marimo",
                "export",
                "ipynb",
                temp_marimo_file_with_md,
                "--sort",
                "top-down",
            ],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        topdown_output = p.stdout.decode()
        snapshot("ipynb_topdown.txt", topdown_output)

        # Outputs should be different since sorting is different
        assert topo_output != topdown_output

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has(),
        reason="This test requires nbformat.",
    )
    def test_export_ipynb_with_outputs(
        self, temp_marimo_file_with_md: str
    ) -> None:
        # Test without outputs (default)
        p = subprocess.run(
            ["marimo", "export", "ipynb", temp_marimo_file_with_md],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        no_outputs = p.stdout.decode()

        # Test with outputs
        p = subprocess.run(
            [
                "marimo",
                "export",
                "ipynb",
                temp_marimo_file_with_md,
                "--include-outputs",
            ],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        with_outputs = p.stdout.decode()
        snapshot("ipynb_with_outputs.txt", with_outputs)

        # Outputs should be different since one includes execution results
        assert no_outputs != with_outputs
