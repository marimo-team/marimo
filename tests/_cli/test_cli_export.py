# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import inspect
import json
import shutil
import subprocess
import sys
import time
from os import path
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from marimo._dependencies.dependencies import DependencyManager
from tests._server.templates.utils import normalize_index_html
from tests.mocks import snapshotter

if TYPE_CHECKING:
    import pathlib

HAS_UV = DependencyManager.which("uv")
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
    def test_cli_export_html_wasm(temp_marimo_file: str) -> None:
        out_dir = Path(temp_marimo_file).parent / "out"
        p = subprocess.run(
            [
                "marimo",
                "export",
                "html-wasm",
                temp_marimo_file,
                "--mode",
                "edit",
                "--output",
                out_dir,
            ],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        html = Path(out_dir / "index.html").read_text()
        assert "<marimo-mode data-mode='edit'" in html
        assert (
            '<marimo-code hidden="" data-show-code="false"></marimo-code>'
            not in html
        )
        assert "<marimo-wasm" in html
        assert Path(out_dir / ".nojekyll").exists()

    @staticmethod
    def test_cli_export_html_wasm_public_folder(temp_marimo_file: str) -> None:
        # Create public folder next to temp file with some content
        public_dir = Path(temp_marimo_file).parent / "public"
        public_dir.mkdir(exist_ok=True)
        (public_dir / "test.txt").write_text("test content")

        out_dir = Path(temp_marimo_file).parent / "out"
        p = subprocess.run(
            [
                "marimo",
                "export",
                "html-wasm",
                temp_marimo_file,
                "--output",
                out_dir,
            ],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        # Verify public folder was copied
        assert (out_dir / "public" / "test.txt").exists()
        assert (out_dir / "public" / "test.txt").read_text() == "test content"

        # Try exporting to the same directory that contains the public folder
        p = subprocess.run(
            [
                "marimo",
                "export",
                "html-wasm",
                temp_marimo_file,
                "--output",
                public_dir.parent,
            ],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()

        # Clean up
        shutil.rmtree(public_dir)

    @staticmethod
    def test_cli_export_html_wasm_output_is_file(
        temp_marimo_file: str,
    ) -> None:
        out_dir = Path(temp_marimo_file).parent / "out_file"
        p = subprocess.run(
            [
                "marimo",
                "export",
                "html-wasm",
                temp_marimo_file,
                "--output",
                str(out_dir / "foo.html"),
            ],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        assert Path(out_dir / "foo.html").exists()
        assert not Path(out_dir / "index.html").exists()
        html = Path(out_dir / "foo.html").read_text()
        assert "<marimo-wasm" in html

    @staticmethod
    def test_cli_export_html_wasm_read(temp_marimo_file: str) -> None:
        out_dir = Path(temp_marimo_file).parent / "out"
        p = subprocess.run(
            [
                "marimo",
                "export",
                "html-wasm",
                temp_marimo_file,
                "--mode",
                "run",
                "--output",
                out_dir,
            ],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        html = Path(out_dir / "index.html").read_text()
        assert "<marimo-mode data-mode='read'" in html
        assert (
            '<marimo-code hidden="" data-show-code="false"></marimo-code>'
            not in html
        )
        assert "<marimo-wasm" in html

    @pytest.mark.skipif(
        # if hangs on watchdog, add a dependency check
        condition=_is_win32(),
        reason="flaky on Windows",
    )
    @staticmethod
    def test_cli_export_html_wasm_watch(temp_marimo_file: str) -> None:
        out_dir = Path(temp_marimo_file).parent / "out"
        p = subprocess.Popen(
            [
                "marimo",
                "export",
                "html-wasm",
                temp_marimo_file,
                "--output",
                out_dir,
                "--watch",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        watch_echo_found = False
        for _ in range(10):  # read 10 lines
            line = p.stdout.readline()
            if not line:
                break
            line_str = line.decode()
            if f"Watching {temp_marimo_file}" in line_str:
                watch_echo_found = True
                break
            time.sleep(0.01)  # avoid flaky test
        assert watch_echo_found is True

        # Modify file
        with open(temp_marimo_file, "a") as f:
            f.write("\n# comment\n")

        assert p.poll() is None
        for _ in range(5):
            line = p.stdout.readline().decode()
            if line:
                assert "Re-exporting" in line
                break
            time.sleep(0.01)

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

    @staticmethod
    def test_export_html_with_errors(
        temp_marimo_file_with_errors: str,
    ) -> None:
        p = subprocess.run(
            ["marimo", "export", "html", temp_marimo_file_with_errors],
            capture_output=True,
        )
        assert p.returncode != 0, p.stderr.decode()
        html = normalize_index_html(p.stdout.decode())
        # Errors but still produces HTML
        assert " division by zero" in p.stderr.decode()
        assert "<marimo-code" in html

    @staticmethod
    def test_export_html_with_multiple_definitions(
        temp_marimo_file_with_multiple_definitions: str,
    ) -> None:
        p = subprocess.run(
            [
                "marimo",
                "export",
                "html",
                temp_marimo_file_with_multiple_definitions,
            ],
            capture_output=True,
        )
        assert p.returncode != 0, p.stderr.decode()
        # Errors but still produces HTML
        assert "MultipleDefinitionError" in p.stderr.decode()
        assert "<marimo-code" in p.stdout.decode()

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

    @staticmethod
    @pytest.mark.skipif(not HAS_UV, reason="uv is required for sandbox tests")
    def test_cli_export_html_sandbox(temp_marimo_file: str) -> None:
        p = subprocess.run(
            [
                "marimo",
                "export",
                "html",
                temp_marimo_file,
                "--sandbox",
            ],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        output = p.stdout.decode()
        # Check for sandbox message
        assert "Running in a sandbox" in output
        assert "uv run --isolated" in output
        html = normalize_index_html(output)
        # Remove folder path
        dirname = path.dirname(temp_marimo_file)
        html = html.replace(dirname, "path")
        assert '<marimo-code hidden=""></marimo-code>' not in html

    @staticmethod
    def test_cli_export_html_sandbox_no_prompt(temp_marimo_file: str) -> None:
        p = subprocess.run(
            [
                "marimo",
                "export",
                "html",
                temp_marimo_file,
                "--no-sandbox",
            ],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()


class TestExportHtmlSmokeTests:
    def assert_not_errored(
        self, p: subprocess.CompletedProcess[bytes]
    ) -> None:
        assert p.returncode == 0, p.stderr.decode()
        assert not any(
            line.startswith("Traceback")
            for line in p.stderr.decode().splitlines()
        )
        assert not any(
            line.startswith("Traceback")
            for line in p.stdout.decode().splitlines()
        )

    def assert_has_errors(self, p: subprocess.CompletedProcess[bytes]) -> None:
        assert p.returncode != 0, p.stderr.decode()
        assert any(
            "Export was successful, but some cells failed to execute" in line
            for line in p.stderr.decode().splitlines()
        ), p.stderr.decode()
        assert not any(
            line.startswith("Traceback")
            for line in p.stdout.decode().splitlines()
        ), p.stdout.decode()

    def test_export_intro_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import intro

        file = tmp_path / "intro.py"
        out = tmp_path / "out.html"
        file.write_text(inspect.getsource(intro), encoding="utf-8")
        p = subprocess.run(
            ["marimo", "export", "html", str(file), "-o", str(out)],
            capture_output=True,
        )
        assert Path(out).exists()
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
        assert Path(out).exists()
        self.assert_not_errored(p)

    def test_export_dataflow_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import dataflow as mod

        file = tmp_path / "mod.py"
        file.write_text(inspect.getsource(mod), encoding="utf-8")
        out = tmp_path / "out.html"
        p = subprocess.run(
            [
                "marimo",
                "export",
                "html",
                str(file),
                "-o",
                str(out),
                "--no-sandbox",
            ],
            capture_output=True,
        )
        self.assert_has_errors(p)

    def test_export_layout_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import layout as mod

        file = tmp_path / "mod.py"
        file.write_text(inspect.getsource(mod), encoding="utf-8")
        out = tmp_path / "out.html"
        p = subprocess.run(
            ["marimo", "export", "html", str(file), "-o", str(out)],
            capture_output=True,
        )
        assert Path(out).exists()
        self.assert_not_errored(p)

    @pytest.mark.skipif(
        condition=not DependencyManager.matplotlib.has(),
        reason="matplotlib is not installed",
    )
    def test_export_plots_tutorial(self, tmp_path: pathlib.Path) -> None:
        from marimo._tutorials import plots as mod

        file = tmp_path / "plots.py"
        file.write_text(inspect.getsource(mod), encoding="utf-8")
        out = tmp_path / "out.html"
        p = subprocess.run(
            ["marimo", "export", "html", str(file), "-o", str(out)],
            capture_output=True,
        )
        assert Path(out).exists()
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
        assert Path(out).exists()
        self.assert_has_errors(p)


class TestExportScript:
    @staticmethod
    def test_export_script(temp_marimo_file: str) -> None:
        p = subprocess.run(
            ["marimo", "export", "script", temp_marimo_file],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        output = p.stdout.decode()
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

    @staticmethod
    def test_export_script_with_multiple_definitions(
        temp_marimo_file_with_multiple_definitions: str,
    ) -> None:
        p = subprocess.run(
            [
                "marimo",
                "export",
                "script",
                temp_marimo_file_with_multiple_definitions,
            ],
            capture_output=True,
        )
        assert p.returncode != 0, (
            "Expected non-zero return code due to multiple definitions"
        )
        error_message = p.stderr.decode()
        assert (
            "MultipleDefinitionError: This app can't be run because it has multiple definitions of the name x"
            in error_message
        )

    @staticmethod
    def test_export_script_with_errors(
        temp_marimo_file_with_errors: str,
    ) -> None:
        p = subprocess.run(
            ["marimo", "export", "script", temp_marimo_file_with_errors],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        output = p.stdout.decode()
        snapshot("script_with_errors.txt", output)

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
        snapshot("markdown.txt", output)

    @staticmethod
    def test_export_markdown_async(temp_async_marimo_file: str) -> None:
        p = subprocess.run(
            ["marimo", "export", "md", temp_async_marimo_file],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        output = p.stdout.decode()
        snapshot("async.txt", output)

    @staticmethod
    def test_export_markdown_broken(temp_unparsable_marimo_file: str) -> None:
        p = subprocess.run(
            ["marimo", "export", "md", temp_unparsable_marimo_file],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        output = p.stdout.decode()
        snapshot("broken.txt", output)

    @staticmethod
    def test_export_markdown_with_errors(
        temp_marimo_file_with_errors: str,
    ) -> None:
        p = subprocess.run(
            ["marimo", "export", "md", temp_marimo_file_with_errors],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        output = p.stdout.decode()
        snapshot("export_markdown_with_errors.txt", output)

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
    @pytest.mark.skipif(
        not DependencyManager.nbformat.has(),
        reason="This test requires nbformat.",
    )
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

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has(),
        reason="This test requires nbformat.",
    )
    def test_export_ipynb_with_multiple_definitions(
        self, temp_marimo_file_with_multiple_definitions: str
    ) -> None:
        p = subprocess.run(
            [
                "marimo",
                "export",
                "ipynb",
                temp_marimo_file_with_multiple_definitions,
                "--include-outputs",
            ],
            capture_output=True,
        )
        assert p.returncode != 0, p.stderr.decode()
        assert "MultipleDefinitionError" in p.stderr.decode()
        assert p.stdout.decode() == ""

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has(),
        reason="This test requires nbformat.",
    )
    def test_export_ipynb_with_errors(
        self, temp_marimo_file_with_errors: str
    ) -> None:
        p = subprocess.run(
            [
                "marimo",
                "export",
                "ipynb",
                temp_marimo_file_with_errors,
                "--include-outputs",
            ],
            capture_output=True,
        )
        assert p.returncode != 0, p.stderr.decode()
        assert " division by zero" in p.stderr.decode()
        output = p.stdout.decode()
        output = _delete_lines_with_files(output)
        snapshot("ipynb_with_errors.txt", output)

    @staticmethod
    @pytest.mark.skipif(
        not HAS_UV or not DependencyManager.nbformat.has(),
        reason="This test requires both uv and nbformat.",
    )
    def test_cli_export_ipynb_sandbox(temp_marimo_file: str) -> None:
        output_file = temp_marimo_file.replace(".py", "_sandbox.ipynb")
        p = subprocess.run(
            [
                "marimo",
                "export",
                "ipynb",
                temp_marimo_file,
                "--sandbox",
                "--include-outputs",
                "--output",
                output_file,
            ],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        output = p.stdout.decode()
        # Check for sandbox message
        assert "Running in a sandbox" in output
        assert "uv run --isolated" in output

    @staticmethod
    @pytest.mark.skipif(
        not HAS_UV or not DependencyManager.nbformat.has(),
        reason="This test requires both uv and nbformat.",
    )
    def test_cli_export_ipynb_sandbox_no_outputs(
        temp_marimo_file: str,
    ) -> None:
        # Should not use sandbox when not including outputs
        p = subprocess.run(
            [
                "marimo",
                "export",
                "ipynb",
                temp_marimo_file,
                "--sandbox",
                "--no-include-outputs",
            ],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
        output = p.stdout.decode()
        # Should be valid JSON since sandbox is not used
        notebook = json.loads(output)
        assert "cells" in notebook
        assert "nbformat" in notebook

    @staticmethod
    def test_cli_export_html_sandbox_no_prompt(temp_marimo_file: str) -> None:
        p = subprocess.run(
            [
                "marimo",
                "export",
                "html",
                temp_marimo_file,
                "--no-sandbox",
            ],
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()


def _delete_lines_with_files(output: str) -> str:
    return "\n".join(
        line for line in output.splitlines() if "File " not in line
    )
