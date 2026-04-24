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
from typing import TYPE_CHECKING, Any
from unittest import mock

import click
import pytest
from click.testing import CliRunner, Result

from marimo._cli.cli import main
from marimo._cli.export.commands import pdf
from marimo._dependencies.dependencies import DependencyManager
from marimo._session.state.serialize import get_session_cache_file
from marimo._utils import async_path
from marimo._utils.paths import marimo_package_path
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

# The in-process CliRunner imports marimo from whatever location Python
# resolves (source tree locally, installed wheel in CI).  The exporter reads
# index.html from marimo_package_path() / "_static", so ensure it exists
# there.  Copy the test-fixture index.html if it's missing.
_STATIC_INDEX = (marimo_package_path() / "_static" / "index.html").resolve()
if not _STATIC_INDEX.exists():
    _STATIC_INDEX.parent.mkdir(parents=True, exist_ok=True)
    _test_index = (
        Path(__file__).resolve().parents[1]
        / "_server"
        / "templates"
        / "data"
        / "index.html"
    )
    shutil.copy(_test_index, _STATIC_INDEX)


def _is_win32() -> bool:
    return sys.platform == "win32"


def _playwright_browsers_installed() -> bool:
    """Check if Playwright Chromium browser binary is actually installed."""
    try:
        import os

        # Playwright stores browsers in PLAYWRIGHT_BROWSERS_PATH or
        # the default cache: ~/.cache/ms-playwright (Linux),
        # ~/Library/Caches/ms-playwright (macOS)
        browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if not browsers_path:
            if sys.platform == "darwin":
                browsers_path = str(
                    Path.home() / "Library" / "Caches" / "ms-playwright"
                )
            elif sys.platform == "win32":
                local = os.environ.get("LOCALAPPDATA", "")
                browsers_path = (
                    str(Path(local) / "ms-playwright") if local else ""
                )
            else:
                browsers_path = str(Path.home() / ".cache" / "ms-playwright")
        p = Path(browsers_path)
        if not p.exists():
            return False
        # Check if any chromium directory exists
        return any(d.name.startswith("chromium") for d in p.iterdir())
    except Exception:
        return False


_runner = CliRunner()


def _run_export(
    export_format: str,
    file: str,
    *extra_args: str,
    stdin: str | None = None,
) -> Result:
    """Helper to run marimo export commands via CliRunner."""
    return _runner.invoke(
        main,
        ["export", export_format, file, *extra_args],
        input=stdin,
    )


def _assert_success(r: Result) -> None:
    # Re-raise unexpected exceptions so failures are clearly surfaced
    if r.exception and not isinstance(r.exception, SystemExit):
        raise r.exception
    assert r.exit_code == 0, r.output


def _assert_failure(r: Result) -> None:
    assert r.exit_code != 0, r.output


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
        html = normalize_index_html(p.output)
        html = _normalize_html_path(html, temp_marimo_file)
        assert '<marimo-code hidden=""></marimo-code>' not in html

    @staticmethod
    def test_cli_export_html_no_code(temp_marimo_file: str) -> None:
        p = _run_export("html", temp_marimo_file, "--no-include-code")
        _assert_success(p)
        html = normalize_index_html(p.output)
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
        assert "{ filename }" not in html
        assert '"mode": "edit"' in html
        assert '<marimo-code hidden=""></marimo-code>' not in html
        assert "<marimo-wasm" in html
        assert '"showAppCode": false' in html
        assert Path(out_dir / ".nojekyll").exists()

    @staticmethod
    def test_cli_export_html_wasm_no_override(temp_marimo_file: str) -> None:
        out_dir = Path(temp_marimo_file).parent / "out"
        out_dir.mkdir()
        Path(out_dir / "index.html").touch()
        with mock.patch(
            "marimo._cli.export.commands.prompt_to_overwrite",
            return_value=False,
        ):
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
            assert "" == html

    @staticmethod
    def test_cli_export_html_wasm_override(temp_marimo_file: str) -> None:
        out_dir = Path(temp_marimo_file).parent / "out"
        out_dir.mkdir()
        Path(out_dir / "index.html").touch()
        with mock.patch(
            "marimo._cli.export.commands.prompt_to_overwrite",
            return_value=True,
        ):
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
            assert "" != html

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
        stderr = p.stderr or ""
        assert "ValueError" not in stderr
        assert "Traceback" not in stderr
        html = normalize_index_html(p.output)
        html = _normalize_html_path(html, temp_async_marimo_file)
        assert '<marimo-code hidden=""></marimo-code>' not in html

    @staticmethod
    def test_export_html_with_errors(
        temp_marimo_file_with_errors: str,
    ) -> None:
        p = _run_export("html", temp_marimo_file_with_errors)
        _assert_failure(p)
        html = normalize_index_html(p.output)
        # Errors but still produces HTML
        assert " division by zero" in p.stderr
        assert "<marimo-code" in html

    @staticmethod
    def test_export_html_with_multiple_definitions(
        temp_marimo_file_with_multiple_definitions: str,
    ) -> None:
        p = _run_export("html", temp_marimo_file_with_multiple_definitions)
        _assert_failure(p)
        # Errors but still produces HTML
        assert "MultipleDefinitionError" in p.stderr
        assert "<marimo-code" in p.output

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
                    "cannot use --watch without providing an output file "
                    "with --output" in line
                )
                break

    @staticmethod
    @pytest.mark.skipif(not HAS_UV, reason="uv is required for sandbox tests")
    def test_cli_export_html_sandbox(temp_marimo_file: str) -> None:
        # Must use subprocess: sandbox re-invokes via uv using sys.argv[1:]
        p = subprocess.run(
            ["marimo", "export", "html", temp_marimo_file, "--sandbox"],
            check=False,
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
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
        output_path = Path(temp_marimo_file).parent / "output.html"

        # First export creates the file
        p1 = _run_export("html", temp_marimo_file, "-o", str(output_path))
        _assert_success(p1)

        # With TTY simulated, "n\n" on stdin causes graceful exit (no overwrite)
        with mock.patch("marimo._cli.utils.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            p2 = _run_export(
                "html", temp_marimo_file, "-o", str(output_path), stdin="n\n"
            )
        assert p2.exit_code == 0, "Expected graceful exit when user answers no"

        # --force skips the prompt entirely
        p3 = _run_export(
            "html", temp_marimo_file, "-o", str(output_path), "--force"
        )
        _assert_success(p3)


class TestExportHtmlSmokeTests:
    def _assert_no_traceback(self, p: Result) -> None:
        """Assert no traceback in stdout or stderr."""
        assert not any(
            line.startswith("Traceback") for line in p.stderr.splitlines()
        )
        assert not any(
            line.startswith("Traceback") for line in p.output.splitlines()
        )

    def _assert_not_errored(self, p: Result) -> None:
        _assert_success(p)
        self._assert_no_traceback(p)

    def _assert_has_errors(self, p: Result) -> None:
        _assert_failure(p)
        assert any(
            "Export was successful, but some cells failed to execute" in line
            for line in p.stderr.splitlines()
        ), p.output
        self._assert_no_traceback(p)

    def _export_tutorial(
        self,
        tmp_path: pathlib.Path,
        module_import: str,
        filename: str = "mod.py",
        extra_args: tuple[str, ...] = (),
    ) -> Result:
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
        p = self._export_tutorial(
            tmp_path, "plots", "plots.py", extra_args=("--no-sandbox",)
        )
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
        snapshot(_get_snapshot_path("script", "script"), p.output)

    @staticmethod
    def test_export_script_async(temp_async_marimo_file: str) -> None:
        p = _run_export("script", temp_async_marimo_file)
        assert p.exit_code == 1, p.output
        assert "Cannot export a notebook with async code to a flat script" in (
            p.output
        )

    @staticmethod
    def test_export_script_with_multiple_definitions(
        temp_marimo_file_with_multiple_definitions: str,
    ) -> None:
        p = _run_export("script", temp_marimo_file_with_multiple_definitions)
        _assert_failure(p)
        # MultipleDefinitionError is uncaught; CliRunner stores it in exception
        error_message = str(p.exception) if p.exception else p.output
        assert "multiple definitions of the name x" in error_message

    @staticmethod
    def test_export_script_with_errors(
        temp_marimo_file_with_errors: str,
    ) -> None:
        p = _run_export("script", temp_marimo_file_with_errors)
        _assert_success(p)
        snapshot(
            _get_snapshot_path("script", "script_with_errors"),
            p.output,
        )

    @staticmethod
    def test_export_script_with_inline_deps(
        temp_sandboxed_marimo_file: str,
    ) -> None:
        p = _run_export("script", temp_sandboxed_marimo_file)
        _assert_success(p)
        output = p.stdout
        assert "# /// script" in output
        assert "polars" in output
        snapshot(_get_snapshot_path("script", "script_sandboxed"), output)

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
                    "cannot use --watch without providing an output file "
                    "with --output" in line
                )
                break


class TestExportMarkdown:
    @staticmethod
    def test_export_markdown(temp_marimo_file: str) -> None:
        p = _run_export("md", temp_marimo_file)
        _assert_success(p)
        snapshot(_get_snapshot_path("md", "markdown"), p.output)

    @staticmethod
    def test_export_markdown_async(temp_async_marimo_file: str) -> None:
        p = _run_export("md", temp_async_marimo_file)
        _assert_success(p)
        snapshot(_get_snapshot_path("md", "async"), p.output)

    @staticmethod
    def test_export_markdown_broken(temp_unparsable_marimo_file: str) -> None:
        p = _run_export("md", temp_unparsable_marimo_file)
        _assert_success(p)
        snapshot(_get_snapshot_path("md", "broken"), p.output)

    @staticmethod
    def test_export_markdown_with_errors(
        temp_marimo_file_with_errors: str,
    ) -> None:
        p = _run_export("md", temp_marimo_file_with_errors)
        _assert_success(p)
        snapshot(
            _get_snapshot_path("md", "export_markdown_with_errors"),
            p.output,
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
                    "cannot use --watch without providing an output file "
                    "with --output" in line
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
        snapshot(_get_snapshot_path("ipynb", "ipynb"), p.output)

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
        topo_output = p.output

        # Test top-down sort
        p = _run_export(
            "ipynb", temp_marimo_file_with_md, "--sort", "top-down"
        )
        _assert_success(p)
        topdown_output = p.output
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
        no_outputs = p.output

        # Test with outputs
        p = _run_export("ipynb", temp_marimo_file_with_md, "--include-outputs")
        _assert_success(p)
        with_outputs = p.output
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
            "ipynb",
            temp_marimo_file_with_media,
            "--include-outputs",
            "--no-sandbox",
        )
        _assert_success(p)
        with_outputs = p.output
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
        output = p.output
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
        output = p.output
        assert "division by zero" in output
        output = delete_lines_with_files(output)
        snapshot(_get_snapshot_path("ipynb", "ipynb_with_errors"), output)

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has(),
        reason="This test requires nbformat.",
    )
    def test_export_ipynb_with_cli_args(
        self, temp_marimo_file_with_md: str
    ) -> None:
        p = _run_export(
            "ipynb",
            temp_marimo_file_with_md,
            "--include-outputs",
            "--",
            "--arg1",
            "foo",
            "--arg2",
            "bar",
        )
        _assert_success(p)

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has(),
        reason="This test requires nbformat.",
    )
    def test_export_ipynb_cli_args_passed_to_export(
        self, temp_marimo_file_with_md: str
    ) -> None:
        from marimo._server.export import ExportResult

        fake_result = ExportResult(
            contents="{}", download_filename="test.ipynb", did_error=False
        )

        async def fake_export(*args: Any, **kwargs: Any) -> ExportResult:
            del args, kwargs
            return fake_result

        with mock.patch(
            "marimo._cli.export.commands.run_app_then_export_as_ipynb",
            side_effect=fake_export,
        ) as mock_export:
            p = _run_export(
                "ipynb",
                temp_marimo_file_with_md,
                "--include-outputs",
                "--",
                "--arg1",
                "foo",
                "--arg2",
                "bar",
            )
            _assert_success(p)

            mock_export.assert_called_once()
            call_kwargs = mock_export.call_args
            assert call_kwargs.kwargs["cli_args"] == {
                "arg1": "foo",
                "arg2": "bar",
            }
            assert call_kwargs.kwargs["argv"] == [
                "--arg1",
                "foo",
                "--arg2",
                "bar",
            ]

    @staticmethod
    @pytest.mark.skipif(
        not HAS_UV or not DependencyManager.nbformat.has(),
        reason="This test requires both uv and nbformat.",
    )
    def test_cli_export_ipynb_sandbox(temp_marimo_file: str) -> None:
        output_file = temp_marimo_file.replace(".py", "_sandbox.ipynb")
        # Must use subprocess: sandbox re-invokes via uv using sys.argv[1:]
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
            check=False,
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode()
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
        output = p.output
        # Should be valid JSON since sandbox is not used
        notebook = json.loads(output)
        assert "cells" in notebook
        assert "nbformat" in notebook

    @staticmethod
    def test_cli_export_html_sandbox_no_prompt(temp_marimo_file: str) -> None:
        p = _run_export("html", temp_marimo_file, "--no-sandbox")
        _assert_success(p)


class TestExportPDF:
    @staticmethod
    def test_export_pdf_rasterize_outputs_default_enabled() -> None:
        rasterize_option = next(
            param for param in pdf.params if param.name == "rasterize_outputs"
        )
        assert isinstance(rasterize_option, click.Option)
        assert rasterize_option.default is True

    @staticmethod
    def test_export_pdf_raster_server_default_static() -> None:
        raster_server_option = next(
            param for param in pdf.params if param.name == "raster_server"
        )
        assert isinstance(raster_server_option, click.Option)
        assert raster_server_option.default == "static"

    @pytest.mark.skipif(
        DependencyManager.nbformat.has() and DependencyManager.nbconvert.has(),
        reason="This test expects PDF export deps to be missing.",
    )
    def test_export_pdf_missing_dependencies(
        self, temp_marimo_file: str
    ) -> None:
        output_file = temp_marimo_file.replace(".py", ".pdf")
        p = _run_export(
            "pdf",
            temp_marimo_file,
            "--output",
            output_file,
            "--no-sandbox",
            "--no-include-inputs",
        )
        _assert_failure(p)
        stderr = p.output
        assert "nbconvert" in stderr
        assert "pip install" in stderr

    @staticmethod
    def test_export_pdf_rasterize_requires_outputs(
        temp_marimo_file: str,
    ) -> None:
        output_file = temp_marimo_file.replace(".py", ".pdf")
        p = _run_export(
            "pdf",
            temp_marimo_file,
            "--output",
            output_file,
            "--no-include-outputs",
            "--rasterize-outputs",
            "--no-sandbox",
        )
        _assert_failure(p)
        stderr = p.output
        assert "Rasterization options require --include-outputs." in stderr

    @staticmethod
    def test_export_pdf_raster_scale_requires_outputs(
        temp_marimo_file: str,
    ) -> None:
        output_file = temp_marimo_file.replace(".py", ".pdf")
        p = _run_export(
            "pdf",
            temp_marimo_file,
            "--output",
            output_file,
            "--no-include-outputs",
            "--raster-scale",
            "2",
            "--no-sandbox",
        )
        _assert_failure(p)
        stderr = p.output
        assert "Rasterization options require --include-outputs." in stderr

    @staticmethod
    def test_export_pdf_raster_server_requires_outputs(
        temp_marimo_file: str,
    ) -> None:
        output_file = temp_marimo_file.replace(".py", ".pdf")
        p = _run_export(
            "pdf",
            temp_marimo_file,
            "--output",
            output_file,
            "--no-include-outputs",
            "--raster-server",
            "live",
            "--no-sandbox",
        )
        _assert_failure(p)
        stderr = p.output
        assert "Rasterization options require --include-outputs." in stderr

    @staticmethod
    def test_export_pdf_passes_preset_to_export_pipeline(
        temp_marimo_file: str,
        tmp_path: Path,
    ) -> None:
        from unittest.mock import AsyncMock, patch

        from marimo._cli.export.commands import pdf as pdf_command

        output_file = tmp_path / "out.pdf"
        runner = CliRunner()
        mock_run_app = AsyncMock(return_value=(b"mock_pdf", False))

        with (
            patch(
                "marimo._cli.export.commands.DependencyManager.require_many"
            ),
            patch(
                "marimo._cli.export.commands.run_app_then_export_as_pdf",
                mock_run_app,
            ),
        ):
            result = runner.invoke(
                pdf_command,
                [
                    "--output",
                    str(output_file),
                    "--as",
                    "slides",
                    "--no-sandbox",
                    "--no-include-outputs",
                    temp_marimo_file,
                ],
            )

        assert result.exit_code == 0
        assert output_file.read_bytes() == b"mock_pdf"
        assert mock_run_app.await_count == 1
        call_kwargs = mock_run_app.await_args.kwargs
        assert call_kwargs["export_as"] == "slides"

    @staticmethod
    def test_export_pdf_slides_shows_live_raster_recommendation(
        temp_marimo_file: str,
        tmp_path: Path,
    ) -> None:
        from unittest.mock import AsyncMock, patch

        from marimo._cli.export.commands import pdf as pdf_command

        output_file = tmp_path / "slides-tip.pdf"
        runner = CliRunner()
        mock_run_app = AsyncMock(return_value=(b"mock_pdf", False))

        with (
            patch(
                "marimo._cli.export.commands.DependencyManager.require_many"
            ),
            patch(
                "marimo._cli.export.commands.DependencyManager.playwright.require"
            ),
            patch(
                "marimo._cli.export.commands.run_app_then_export_as_pdf",
                mock_run_app,
            ),
        ):
            result = runner.invoke(
                pdf_command,
                [
                    "--output",
                    str(output_file),
                    "--as",
                    "slides",
                    "--no-sandbox",
                    temp_marimo_file,
                ],
            )

        assert result.exit_code == 0
        assert "For --as=slides, prefer --raster-server=live" in result.output
        assert mock_run_app.await_count == 1
        call_kwargs = mock_run_app.await_args.kwargs
        assert call_kwargs["rasterization_options"].server_mode == "static"

    @staticmethod
    def test_export_pdf_shows_slides_hint_when_preset_missing(
        temp_marimo_file: str,
        tmp_path: Path,
    ) -> None:
        from unittest.mock import AsyncMock, patch

        from marimo._cli.export.commands import pdf as pdf_command

        output_file = tmp_path / "hint.pdf"
        runner = CliRunner()
        mock_run_app = AsyncMock(return_value=(b"mock_pdf", False))

        with (
            patch(
                "marimo._cli.export.commands.DependencyManager.require_many"
            ),
            patch(
                "marimo._cli.export.commands.notebook_uses_slides_layout",
                return_value=True,
            ),
            patch(
                "marimo._cli.export.commands.run_app_then_export_as_pdf",
                mock_run_app,
            ),
        ):
            result = runner.invoke(
                pdf_command,
                [
                    "--output",
                    str(output_file),
                    "--no-sandbox",
                    "--no-include-outputs",
                    temp_marimo_file,
                ],
            )

        assert result.exit_code == 0
        assert "Use --as=slides for slide-style PDF export." in result.output
        assert mock_run_app.await_count == 1
        call_kwargs = mock_run_app.await_args.kwargs
        assert call_kwargs["export_as"] is None

    @staticmethod
    def test_export_pdf_reports_stage_status_updates(
        temp_marimo_file: str,
        tmp_path: Path,
    ) -> None:
        from unittest.mock import AsyncMock, patch

        from marimo._cli.export.commands import pdf as pdf_command
        from marimo._server.export._status import PDFExportStatusEvent

        output_file = tmp_path / "status.pdf"
        runner = CliRunner()

        async def fake_run_app(
            *args: Any, **kwargs: Any
        ) -> tuple[bytes, bool]:
            del args
            status_callback = kwargs["status_callback"]
            status_callback(
                PDFExportStatusEvent(
                    phase="execute",
                    message="executing notebook...",
                )
            )
            status_callback(
                PDFExportStatusEvent(
                    phase="raster",
                    message="rasterizing interactive outputs...",
                    current=2,
                    total=7,
                )
            )
            status_callback(
                PDFExportStatusEvent(
                    phase="prepare",
                    message="serializing notebook for PDF rendering...",
                )
            )
            status_callback(
                PDFExportStatusEvent(
                    phase="render",
                    message="rendering PDF via WebPDF...",
                )
            )
            status_callback(
                PDFExportStatusEvent(
                    phase="complete",
                    message="done.",
                )
            )
            return b"mock_pdf", False

        mock_run_app = AsyncMock(side_effect=fake_run_app)

        with (
            patch(
                "marimo._cli.export.commands.DependencyManager.require_many"
            ),
            patch(
                "marimo._cli.export.commands.DependencyManager.playwright.require"
            ),
            patch(
                "marimo._cli.export.commands.run_app_then_export_as_pdf",
                mock_run_app,
            ),
        ):
            result = runner.invoke(
                pdf_command,
                [
                    "--output",
                    str(output_file),
                    "--no-sandbox",
                    temp_marimo_file,
                ],
            )

        assert result.exit_code == 0
        assert output_file.read_bytes() == b"mock_pdf"
        assert "Exporting PDF: executing notebook..." in result.output
        assert (
            "Exporting PDF: rasterizing interactive outputs [2/7]..."
            in result.output
        )
        assert (
            "Exporting PDF: serializing notebook for PDF rendering..."
            in result.output
        )
        assert "Exporting PDF: rendering PDF via WebPDF..." in result.output
        assert "Exporting PDF: done." in result.output
        assert mock_run_app.await_count == 1


@pytest.mark.skipif(
    not DependencyManager.playwright.has(),
    reason="This test requires playwright.",
)
@pytest.mark.skipif(
    DependencyManager.playwright.has()
    and not _playwright_browsers_installed(),
    reason="Playwright browsers are not installed.",
)
class TestExportThumbnail:
    def test_export_thumbnail(self, temp_marimo_file: str) -> None:
        p = _run_export("thumbnail", temp_marimo_file)
        _assert_success(p)

    def test_export_thumbnail_with_args(self, temp_marimo_file: str) -> None:
        p = _run_export("thumbnail", temp_marimo_file, "--", "--foo", "123")
        _assert_success(p)


class TestExportSession:
    @staticmethod
    def test_export_session(temp_marimo_file: str) -> None:
        p = _run_export("session", temp_marimo_file)
        _assert_success(p)

        session_file = get_session_cache_file(Path(temp_marimo_file))
        assert session_file.exists()
        data = json.loads(session_file.read_text(encoding="utf-8"))
        assert data["version"] == "1"
        assert len(data["cells"]) > 0

    @staticmethod
    def test_export_session_with_args(temp_marimo_file: str) -> None:
        p = _run_export("session", temp_marimo_file, "--", "--foo", "123")
        _assert_success(p)

        session_file = get_session_cache_file(Path(temp_marimo_file))
        assert session_file.exists()

    @staticmethod
    def test_export_session_default_skips_up_to_date(
        temp_marimo_file: str,
    ) -> None:
        p = _run_export("session", temp_marimo_file)
        _assert_success(p)

        session_file = get_session_cache_file(Path(temp_marimo_file))
        existing = json.loads(session_file.read_text(encoding="utf-8"))
        existing["custom"] = "keep-me"
        session_file.write_text(
            json.dumps(existing, indent=2), encoding="utf-8"
        )

        p = _run_export("session", temp_marimo_file)
        _assert_success(p)

        unchanged = json.loads(session_file.read_text(encoding="utf-8"))
        assert unchanged.get("custom") == "keep-me"
        assert "skip" in p.output

    @staticmethod
    def test_export_session_force_overwrite_rewrites_up_to_date(
        temp_marimo_file: str,
    ) -> None:
        p = _run_export("session", temp_marimo_file)
        _assert_success(p)

        session_file = get_session_cache_file(Path(temp_marimo_file))
        existing = json.loads(session_file.read_text(encoding="utf-8"))
        existing["custom"] = "remove-me"
        session_file.write_text(
            json.dumps(existing, indent=2), encoding="utf-8"
        )

        p = _run_export("session", temp_marimo_file, "--force-overwrite")
        _assert_success(p)

        data = json.loads(session_file.read_text(encoding="utf-8"))
        assert data["version"] == "1"
        assert len(data["cells"]) > 0
        assert "custom" not in data

    @staticmethod
    def test_export_session_default_overwrites_stale(
        temp_marimo_file: str,
    ) -> None:
        p = _run_export("session", temp_marimo_file)
        _assert_success(p)

        notebook_path = Path(temp_marimo_file)
        session_file = get_session_cache_file(notebook_path)
        before = json.loads(session_file.read_text(encoding="utf-8"))

        notebook_path.write_text(
            notebook_path.read_text(encoding="utf-8").replace(
                "slider = mo.ui.slider(0, 10)",
                "slider = mo.ui.slider(0, 11)",
            ),
            encoding="utf-8",
        )

        p = _run_export("session", temp_marimo_file)
        _assert_success(p)

        after = json.loads(session_file.read_text(encoding="utf-8"))
        assert [c["code_hash"] for c in before["cells"]] != [
            c["code_hash"] for c in after["cells"]
        ]

    def test_export_session_directory_default_skips_up_to_date(
        self,
        tmp_path: Path,
        temp_marimo_file: str,
    ) -> None:
        notebook_dir = tmp_path / "notebooks"
        notebook_dir.mkdir()
        code = Path(temp_marimo_file).read_text(encoding="utf-8")
        first = notebook_dir / "first.py"
        second = notebook_dir / "second.py"
        first.write_text(code, encoding="utf-8")
        second.write_text(code, encoding="utf-8")

        p = _run_export("session", str(first))
        _assert_success(p)

        first_session = get_session_cache_file(first)
        existing = json.loads(first_session.read_text(encoding="utf-8"))
        existing["custom"] = "keep-me"
        first_session.write_text(
            json.dumps(existing, indent=2), encoding="utf-8"
        )

        p = _run_export("session", str(notebook_dir))
        _assert_success(p)

        second_session = get_session_cache_file(second)
        first_data = json.loads(first_session.read_text(encoding="utf-8"))
        assert first_data.get("custom") == "keep-me"
        assert second_session.exists()
        data = json.loads(second_session.read_text(encoding="utf-8"))
        assert data["version"] == "1"

    @staticmethod
    def test_export_session_ignores_second_positional_target(
        temp_marimo_file: str,
        temp_async_marimo_file: str,
    ) -> None:
        p = _run_export(
            "session",
            temp_marimo_file,
            temp_async_marimo_file,
        )
        _assert_success(p)

        first_session = get_session_cache_file(Path(temp_marimo_file))
        second_session = get_session_cache_file(Path(temp_async_marimo_file))
        assert first_session.exists()
        assert not second_session.exists()

    @staticmethod
    def test_export_session_directory(
        tmp_path: Path,
        temp_marimo_file: str,
    ) -> None:
        notebook_dir = tmp_path / "notebooks"
        notebook_dir.mkdir()
        code = Path(temp_marimo_file).read_text(encoding="utf-8")
        first = notebook_dir / "first.py"
        second = notebook_dir / "second.py"
        first.write_text(code, encoding="utf-8")
        second.write_text(code, encoding="utf-8")

        p = _run_export("session", str(notebook_dir))
        _assert_success(p)

        first_session = get_session_cache_file(first)
        second_session = get_session_cache_file(second)
        assert first_session.exists()
        assert second_session.exists()

    @staticmethod
    def test_export_session_with_errors_writes_snapshot(
        temp_marimo_file_with_errors: str,
    ) -> None:
        p = _run_export("session", temp_marimo_file_with_errors)
        _assert_failure(p)

        session_file = get_session_cache_file(
            Path(temp_marimo_file_with_errors)
        )
        assert session_file.exists()

    @staticmethod
    def test_export_session_default_skips_if_previous_snapshot_has_errors(
        temp_marimo_file_with_errors: str,
    ) -> None:
        session_file = get_session_cache_file(
            Path(temp_marimo_file_with_errors)
        )

        first = _run_export("session", temp_marimo_file_with_errors)
        _assert_failure(first)
        assert session_file.exists()

        existing = json.loads(session_file.read_text(encoding="utf-8"))
        existing["custom"] = "should-be-overwritten"
        session_file.write_text(
            json.dumps(existing, indent=2),
            encoding="utf-8",
        )

        second = _run_export("session", temp_marimo_file_with_errors)
        _assert_success(second)
        assert "skip" in second.output
        unchanged = json.loads(session_file.read_text(encoding="utf-8"))
        assert unchanged.get("custom") == "should-be-overwritten"

    @staticmethod
    def test_export_session_continue_on_error_default(
        tmp_path: Path,
        temp_marimo_file: str,
        temp_marimo_file_with_errors: str,
    ) -> None:
        notebook_dir = tmp_path / "notebooks"
        notebook_dir.mkdir()
        good = notebook_dir / "good.py"
        bad = notebook_dir / "bad.py"
        good.write_text(
            Path(temp_marimo_file).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        bad.write_text(
            Path(temp_marimo_file_with_errors).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        p = _run_export("session", str(notebook_dir))
        _assert_failure(p)

        good_session = get_session_cache_file(good)
        bad_session = get_session_cache_file(bad)
        assert good_session.exists()
        assert bad_session.exists()


class TestClickArgsParsing:
    """
    Tests below are technically testing Click more than Marimo. This was created as part of an investigation into
    the Click option to allow interspersed arguments or not, and the presence of "--" in the `args` parameter.

    In review, we discussed leaving some of the tests behind to continue illustrating. They can also act as a sort of
    sandbox to try alternative approaches.
    """

    @staticmethod
    def _params(
        command, expected_name, expected_args, expected_opt
    ) -> tuple[Any, ...]:
        return pytest.param(
            command,
            expected_name,
            expected_args,
            expected_opt,
            id=f"`test_command {' '.join(command)}`",
        )

    @pytest.mark.parametrize(
        (
            "command",
            "expected_name",
            "expected_args",
            "expected_opt",
        ),
        [
            _params(["nb.py"], "nb.py", (), False),
            _params(["--opt", "nb.py"], "nb.py", (), True),
            _params(["nb.py", "--opt"], "nb.py", (), True),
            _params(
                ["nb.py", "--", "--foo", "123"],
                "nb.py",
                ("--foo", "123"),
                False,
            ),
            _params(
                ["--opt", "nb.py", "--", "--foo", "123"],
                "nb.py",
                ("--foo", "123"),
                True,
            ),
            _params(
                ["nb.py", "--opt", "--", "--foo", "123"],
                "nb.py",
                ("--foo", "123"),
                True,
            ),
        ],
    )
    def test_click_args_parsing(
        self,
        command: list[str],
        expected_name: str,
        expected_args: tuple[str, ...],
        expected_opt: bool,
    ) -> None:
        @click.command("test_command")
        @click.argument("name")
        @click.option("--opt/--no-opt", default=False)
        @click.argument("args", nargs=-1, type=click.UNPROCESSED)
        def test_command(
            name: str, opt: bool, args: tuple[str, ...]
        ) -> tuple[str, tuple[str, ...], bool]:
            return name, args, opt

        assert test_command.main(command, standalone_mode=False) == (
            expected_name,
            expected_args,
            expected_opt,
        )
