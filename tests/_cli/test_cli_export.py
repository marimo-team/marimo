# Copyright 2026 Marimo. All rights reserved.
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
from marimo._utils import async_path
from marimo._utils.platform import is_windows
from tests._server.templates.utils import normalize_index_html
from tests.mocks import (
    _sanitize_version,
    delete_lines_with_files,
    simplify_images,
    simplify_plotly,
    snapshotter,
)

if TYPE_CHECKING:
    import pathlib

HAS_UV = DependencyManager.which("uv")
snapshot = snapshotter(__file__)


def _is_win32() -> bool:
    return sys.platform == "win32"


def _run_export(
    export_format: str,
    file: str,
    *extra_args: str,
    capture_output: bool = True,
    input_data: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Helper to run marimo export commands."""
    cmd = ["marimo", "export", export_format, file, *extra_args]
    return subprocess.run(cmd, capture_output=capture_output, input=input_data)


def _assert_success(p: subprocess.CompletedProcess[bytes]) -> None:
    assert p.returncode == 0, p.stderr.decode()


def _assert_failure(p: subprocess.CompletedProcess[bytes]) -> None:
    assert p.returncode != 0, p.stderr.decode()


def _get_snapshot_path(export_format: str, name: str) -> str:
    """Get snapshot path following the pattern export/<format>/<name>.txt"""
    return f"export/{export_format}/{name}.txt"


def _normalize_html_path(html: str, temp_file: str) -> str:
    """Normalize HTML by removing the temporary file's directory path."""
    dirname = path.dirname(temp_file)
    return html.replace(dirname, "path")


class TestExportHTML:
    @staticmethod
    def test_cli_export_html(temp_marimo_file: str) -> None:
        p = _run_export("html", temp_marimo_file)
        _assert_success(p)
        html = normalize_index_html(p.stdout.decode())
        html = _normalize_html_path(html, temp_marimo_file)
        assert '<marimo-code hidden=""></marimo-code>' not in html

    @staticmethod
    def test_cli_export_html_no_code(temp_marimo_file: str) -> None:
        p = _run_export("html", temp_marimo_file, "--no-include-code")
        _assert_success(p)
        html = normalize_index_html(p.stdout.decode())
        html = _normalize_html_path(html, temp_marimo_file)
        assert '<marimo-code hidden=""></marimo-code>' in html

    @staticmethod
    def test_cli_export_html_wasm(temp_marimo_file: str) -> None:
        out_dir = Path(temp_marimo_file).parent / "out"
        p = _run_export(
            "html-wasm",
            temp_marimo_file,
            "--mode",
            "edit",
            "--output",
            str(out_dir),
        )
        _assert_success(p)
        html = Path(out_dir / "index.html").read_text()
        assert '"mode": "edit"' in html
        assert '<marimo-code hidden=""></marimo-code>' not in html
        assert "<marimo-wasm" in html
        assert '"showAppCode": false' in html
        assert Path(out_dir / ".nojekyll").exists()

    @staticmethod
    def test_cli_export_html_wasm_public_folder(temp_marimo_file: str) -> None:
        # Create public folder next to temp file with some content
        public_dir = Path(temp_marimo_file).parent / "public"
        public_dir.mkdir(exist_ok=True)
        (public_dir / "test.txt").write_text("test content")

        out_dir = Path(temp_marimo_file).parent / "out"
        p = _run_export(
            "html-wasm", temp_marimo_file, "--output", str(out_dir)
        )
        _assert_success(p)
        # Verify public folder was copied
        assert (out_dir / "public" / "test.txt").exists()
        assert (out_dir / "public" / "test.txt").read_text() == "test content"

        # Try exporting to the same directory that contains the public folder
        p = _run_export(
            "html-wasm", temp_marimo_file, "--output", str(public_dir.parent)
        )
        _assert_success(p)

        # Clean up
        shutil.rmtree(public_dir)

    @staticmethod
    def test_cli_export_html_wasm_cloudflare(temp_marimo_file: str) -> None:
        out_dir = Path(temp_marimo_file).parent / "cloudflare" / "out"
        p = _run_export(
            "html-wasm",
            temp_marimo_file,
            "--output",
            str(out_dir),
            "--include-cloudflare",
        )
        _assert_success(p)

        # Verify Cloudflare files were created
        assert (out_dir.parent / "index.js").exists()
        assert (out_dir.parent / "wrangler.jsonc").exists()

        # Verify index.js content
        index_js = (out_dir.parent / "index.js").read_text()
        assert "env.ASSETS.fetch(request)" in index_js

        # Verify wrangler.jsonc content
        wrangler = (out_dir.parent / "wrangler.jsonc").read_text()
        assert "name" in wrangler
        assert "main" in wrangler

    @staticmethod
    def test_cli_export_html_wasm_output_is_file(
        temp_marimo_file: str,
    ) -> None:
        out_dir = Path(temp_marimo_file).parent / "out_file"
        output_path = str(out_dir / "foo.html")
        p = _run_export("html-wasm", temp_marimo_file, "--output", output_path)
        _assert_success(p)
        assert Path(out_dir / "foo.html").exists()
        assert not Path(out_dir / "index.html").exists()
        html = Path(out_dir / "foo.html").read_text()
        assert "<marimo-wasm" in html

    @staticmethod
    def test_cli_export_html_wasm_read(temp_marimo_file: str) -> None:
        out_dir = Path(temp_marimo_file).parent / "out"
        p = _run_export(
            "html-wasm",
            temp_marimo_file,
            "--mode",
            "run",
            "--output",
            str(out_dir),
        )
        _assert_success(p)
        html = Path(out_dir / "index.html").read_text()
        assert '"mode": "read"' in html
        assert '<marimo-code hidden=""></marimo-code>' not in html
        assert '"showAppCode": false' in html
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
        p = _run_export("html", temp_async_marimo_file)
        _assert_success(p)
        stderr = p.stderr.decode()
        assert "ValueError" not in stderr
        assert "Traceback" not in stderr
        html = normalize_index_html(p.stdout.decode())
        html = _normalize_html_path(html, temp_async_marimo_file)
        assert '<marimo-code hidden=""></marimo-code>' not in html

    @staticmethod
    def test_export_html_with_errors(
        temp_marimo_file_with_errors: str,
    ) -> None:
        p = _run_export("html", temp_marimo_file_with_errors)
        _assert_failure(p)
        html = normalize_index_html(p.stdout.decode())
        # Errors but still produces HTML
        assert " division by zero" in p.stderr.decode()
        assert "<marimo-code" in html

    @staticmethod
    def test_export_html_with_multiple_definitions(
        temp_marimo_file_with_multiple_definitions: str,
    ) -> None:
        p = _run_export("html", temp_marimo_file_with_multiple_definitions)
        _assert_failure(p)
        # Errors but still produces HTML
        assert "MultipleDefinitionError" in p.stderr.decode()
        assert "<marimo-code" in p.stdout.decode()

    @pytest.mark.skipif(
        condition=DependencyManager.watchdog.has(),
        reason="hangs when watchdog is installed",
    )
    async def test_export_watch(self, temp_marimo_file: str) -> None:
        temp_out_file = temp_marimo_file.replace(".py", ".html")
        p = subprocess.Popen(  # noqa: ASYNC220
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

        assert not await async_path.exists(temp_out_file)

        # Modify file
        with open(temp_marimo_file, "a") as f:  # noqa: ASYNC230
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
        p = _run_export("html", temp_marimo_file, "--sandbox")
        _assert_success(p)
        output = p.stderr.decode()
        # Check for sandbox message
        assert "Running in a sandbox" in output
        assert "run --isolated" in output
        html = normalize_index_html(output)
        html = _normalize_html_path(html, temp_marimo_file)
        assert '<marimo-code hidden=""></marimo-code>' not in html

    @staticmethod
    def test_cli_export_html_sandbox_no_prompt(temp_marimo_file: str) -> None:
        p = _run_export("html", temp_marimo_file, "--no-sandbox")
        _assert_success(p)

    @staticmethod
    def test_cli_export_html_force_overwrite(temp_marimo_file: str) -> None:
        """
        Test that the --force/-f flag allows overwriting an existing file
        using a simple, error-free notebook.
        """
        p1 = _run_export("html", temp_marimo_file)
        _assert_success(p1)
        html = normalize_index_html(p1.stdout.decode())
        html = _normalize_html_path(html, temp_marimo_file)
        assert '<marimo-code hidden=""></marimo-code>' not in html
        output_path = Path(temp_marimo_file).parent / "output.html"

        p2 = _run_export(
            "html", temp_marimo_file, "-o", str(output_path), input_data=b"n\n"
        )
        assert p2.returncode == 0, "Expected a graceful exit with no errors"

        p3 = _run_export(
            "html", temp_marimo_file, "-o", str(output_path), "--force"
        )
        _assert_success(p3)


class TestExportHtmlSmokeTests:
    def _assert_no_traceback(
        self, p: subprocess.CompletedProcess[bytes]
    ) -> None:
        """Assert no traceback in stdout or stderr."""
        assert not any(
            line.startswith("Traceback")
            for line in p.stderr.decode().splitlines()
        )
        assert not any(
            line.startswith("Traceback")
            for line in p.stdout.decode().splitlines()
        )

    def _assert_not_errored(
        self, p: subprocess.CompletedProcess[bytes]
    ) -> None:
        _assert_success(p)
        self._assert_no_traceback(p)

    def _assert_has_errors(
        self, p: subprocess.CompletedProcess[bytes]
    ) -> None:
        _assert_failure(p)
        assert any(
            "Export was successful, but some cells failed to execute" in line
            for line in p.stderr.decode().splitlines()
        ), p.stderr.decode()
        self._assert_no_traceback(p)

    def _export_tutorial(
        self,
        tmp_path: pathlib.Path,
        module_import: str,
        filename: str = "mod.py",
        extra_args: tuple[str, ...] = (),
    ) -> subprocess.CompletedProcess[bytes]:
        """Helper to export a tutorial module to HTML."""
        module = __import__(
            f"marimo._tutorials.{module_import}",
            fromlist=[module_import],
        )
        file = tmp_path / filename
        out = tmp_path / "out.html"
        file.write_text(inspect.getsource(module), encoding="utf-8")
        p = _run_export("html", str(file), "-o", str(out), *extra_args)
        assert Path(out).exists()
        return p

    def test_export_intro_tutorial(self, tmp_path: pathlib.Path) -> None:
        p = self._export_tutorial(tmp_path, "intro", "intro.py")
        self._assert_not_errored(p)

    def test_export_ui_tutorial(self, tmp_path: pathlib.Path) -> None:
        p = self._export_tutorial(tmp_path, "ui")
        self._assert_not_errored(p)

    def test_export_dataflow_tutorial(self, tmp_path: pathlib.Path) -> None:
        p = self._export_tutorial(
            tmp_path, "dataflow", extra_args=("--no-sandbox",)
        )
        self._assert_has_errors(p)

    def test_export_layout_tutorial(self, tmp_path: pathlib.Path) -> None:
        p = self._export_tutorial(tmp_path, "layout")
        self._assert_not_errored(p)

    @pytest.mark.skipif(
        condition=not DependencyManager.matplotlib.has(),
        reason="matplotlib is not installed",
    )
    def test_export_plots_tutorial(self, tmp_path: pathlib.Path) -> None:
        p = self._export_tutorial(tmp_path, "plots", "plots.py")
        self._assert_not_errored(p)

    def test_export_marimo_for_jupyter_users(
        self, tmp_path: pathlib.Path
    ) -> None:
        p = self._export_tutorial(tmp_path, "for_jupyter_users")
        self._assert_has_errors(p)


class TestExportScript:
    @staticmethod
    def test_export_script(temp_marimo_file: str) -> None:
        p = _run_export("script", temp_marimo_file)
        _assert_success(p)
        snapshot(_get_snapshot_path("script", "script"), p.stdout.decode())

    @staticmethod
    def test_export_script_async(temp_async_marimo_file: str) -> None:
        p = _run_export("script", temp_async_marimo_file)
        assert p.returncode == 2, p.stderr.decode()
        assert (
            "Cannot export a notebook with async code to a flat script"
            in p.stderr.decode()
        )

    @staticmethod
    def test_export_script_with_multiple_definitions(
        temp_marimo_file_with_multiple_definitions: str,
    ) -> None:
        p = _run_export("script", temp_marimo_file_with_multiple_definitions)
        _assert_failure(p)
        error_message = p.stderr.decode()
        assert (
            "MultipleDefinitionError: This app can't be run because it has multiple definitions of the name x"
            in error_message
        )

    @staticmethod
    def test_export_script_with_errors(
        temp_marimo_file_with_errors: str,
    ) -> None:
        p = _run_export("script", temp_marimo_file_with_errors)
        _assert_success(p)
        snapshot(
            _get_snapshot_path("script", "script_with_errors"),
            p.stdout.decode(),
        )

    @pytest.mark.skipif(
        condition=DependencyManager.watchdog.has() or _is_win32(),
        reason="hangs when watchdog is installed, flaky on Windows",
    )
    async def test_export_watch_script(self, temp_marimo_file: str) -> None:
        temp_out_file = temp_marimo_file.replace(".py", ".script.py")
        p = subprocess.Popen(  # noqa: ASYNC220
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

        assert not await async_path.exists(temp_out_file)

        # Modify file
        with open(temp_marimo_file, "a") as f:  # noqa: ASYNC230
            f.write("\n# comment\n")

        assert p.poll() is None
        # Wait for rebuild
        while True:
            line = p.stdout.readline().decode()
            if line:
                assert "Re-exporting" in line
                break

        await asyncio.sleep(0.1)
        assert await async_path.exists(temp_out_file)

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
        p = _run_export("md", temp_marimo_file)
        _assert_success(p)
        snapshot(_get_snapshot_path("md", "markdown"), p.stdout.decode())

    @staticmethod
    def test_export_markdown_async(temp_async_marimo_file: str) -> None:
        p = _run_export("md", temp_async_marimo_file)
        _assert_success(p)
        snapshot(_get_snapshot_path("md", "async"), p.stdout.decode())

    @staticmethod
    def test_export_markdown_broken(temp_unparsable_marimo_file: str) -> None:
        p = _run_export("md", temp_unparsable_marimo_file)
        _assert_success(p)
        snapshot(_get_snapshot_path("md", "broken"), p.stdout.decode())

    @staticmethod
    def test_export_markdown_with_errors(
        temp_marimo_file_with_errors: str,
    ) -> None:
        p = _run_export("md", temp_marimo_file_with_errors)
        _assert_success(p)
        snapshot(
            _get_snapshot_path("md", "export_markdown_with_errors"),
            p.stdout.decode(),
        )

    @pytest.mark.skipif(
        condition=DependencyManager.watchdog.has() or _is_win32(),
        reason="hangs when watchdog is installed, flaky on Windows",
    )
    async def test_export_watch_markdown(self, temp_marimo_file: str) -> None:
        temp_out_file = temp_marimo_file.replace(".py", ".md")
        p = subprocess.Popen(  # noqa: ASYNC220
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

        assert not await async_path.exists(temp_out_file)

        # Modify file
        with open(temp_marimo_file, "a") as f:  # noqa: ASYNC230
            f.write("\n# comment\n")

        assert p.poll() is None
        # Wait for rebuild
        while True:
            line = p.stdout.readline().decode()
            if line:
                assert "Re-exporting" in line
                break

        await asyncio.sleep(0.1)
        assert await async_path.exists(temp_out_file)

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
        p = _run_export("ipynb", temp_marimo_file_with_md)
        _assert_success(p)
        # ipynb has non-deterministic ids
        snapshot(_get_snapshot_path("ipynb", "ipynb"), p.stdout.decode())

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has(),
        reason="This test requires nbformat.",
    )
    def test_export_ipynb_sort_modes(
        self, temp_marimo_file_with_md: str
    ) -> None:
        # Test topological sort (default)
        p = _run_export("ipynb", temp_marimo_file_with_md)
        _assert_success(p)
        topo_output = p.stdout.decode()

        # Test top-down sort
        p = _run_export(
            "ipynb", temp_marimo_file_with_md, "--sort", "top-down"
        )
        _assert_success(p)
        topdown_output = p.stdout.decode()
        snapshot(_get_snapshot_path("ipynb", "ipynb_topdown"), topdown_output)

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
        p = _run_export("ipynb", temp_marimo_file_with_md)
        _assert_success(p)
        no_outputs = p.stdout.decode()

        # Test with outputs
        p = _run_export("ipynb", temp_marimo_file_with_md, "--include-outputs")
        _assert_success(p)
        with_outputs = p.stdout.decode()
        snapshot(
            _get_snapshot_path("ipynb", "ipynb_with_outputs"), with_outputs
        )

        # Outputs should be different since one includes execution results
        assert no_outputs != with_outputs

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has(),
        reason="This test requires nbformat.",
    )
    def test_export_ipynb_with_media_outputs(
        self, temp_marimo_file_with_media: str
    ) -> None:
        # Test with outputs
        p = _run_export(
            "ipynb", temp_marimo_file_with_media, "--include-outputs"
        )
        _assert_success(p)
        with_outputs = p.stdout.decode()
        with_outputs = simplify_images(with_outputs)
        with_outputs = simplify_plotly(with_outputs)
        with_outputs = _sanitize_version(with_outputs)
        snapshot(
            _get_snapshot_path("ipynb", "ipynb_with_media_outputs"),
            with_outputs.strip(),
        )

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has(),
        reason="This test requires nbformat.",
    )
    def test_export_ipynb_with_multiple_definitions(
        self, temp_marimo_file_with_multiple_definitions: str
    ) -> None:
        p = _run_export(
            "ipynb",
            temp_marimo_file_with_multiple_definitions,
            "--include-outputs",
        )
        _assert_failure(p)
        # Error is now captured in the ipynb output as a proper Jupyter error
        output = p.stdout.decode()
        assert "multiple-defs" in output
        assert "was defined by another cell" in output

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has() or is_windows(),
        reason="This test requires nbformat. Or windows.",
    )
    def test_export_ipynb_with_errors(
        self, temp_marimo_file_with_errors: str
    ) -> None:
        p = _run_export(
            "ipynb", temp_marimo_file_with_errors, "--include-outputs"
        )
        _assert_failure(p)
        # Error is now captured in the ipynb output (stdout) as a proper
        # Jupyter error output, not printed to stderr
        output = p.stdout.decode()
        assert "division by zero" in output
        output = delete_lines_with_files(output)
        snapshot(_get_snapshot_path("ipynb", "ipynb_with_errors"), output)

    @staticmethod
    @pytest.mark.skipif(
        not HAS_UV or not DependencyManager.nbformat.has(),
        reason="This test requires both uv and nbformat.",
    )
    def test_cli_export_ipynb_sandbox(temp_marimo_file: str) -> None:
        output_file = temp_marimo_file.replace(".py", "_sandbox.ipynb")
        p = _run_export(
            "ipynb",
            temp_marimo_file,
            "--sandbox",
            "--include-outputs",
            "--output",
            output_file,
        )
        _assert_success(p)
        output = p.stderr.decode()
        # Check for sandbox message
        assert "Running in a sandbox" in output
        assert "run --isolated" in output

    @staticmethod
    @pytest.mark.skipif(
        not HAS_UV or not DependencyManager.nbformat.has(),
        reason="This test requires both uv and nbformat.",
    )
    def test_cli_export_ipynb_sandbox_no_outputs(
        temp_marimo_file: str,
    ) -> None:
        # Should not use sandbox when not including outputs
        p = _run_export(
            "ipynb",
            temp_marimo_file,
            "--sandbox",
            "--no-include-outputs",
        )
        _assert_success(p)
        output = p.stdout.decode()
        # Should be valid JSON since sandbox is not used
        notebook = json.loads(output)
        assert "cells" in notebook
        assert "nbformat" in notebook

    @staticmethod
    def test_cli_export_html_sandbox_no_prompt(temp_marimo_file: str) -> None:
        p = _run_export("html", temp_marimo_file, "--no-sandbox")
        _assert_success(p)
