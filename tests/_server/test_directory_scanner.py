# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from marimo._server.files.directory_scanner import (
    DirectoryScanner,
    is_marimo_app,
)
from marimo._server.models.files import FileInfo

if TYPE_CHECKING:
    from pathlib import Path

MARIMO_APP = "import marimo\napp = marimo.App()\n"
MARIMO_MD = "---\nmarimo-version: 0.1.0\n---\n"


def _write(path: Path, content: str) -> Path:
    path.write_text(content)
    return path


def _file_names(files: list[FileInfo]) -> list[str]:
    return [f.name for f in files if not f.is_directory]


def _count_files(files: list[FileInfo]) -> int:
    return sum(
        _count_files(f.children or []) if f.is_directory else 1 for f in files
    )


def test_python_app_detected(tmp_path: Path):
    f = _write(tmp_path / "app.py", MARIMO_APP)
    assert is_marimo_app(str(f))


def test_python_non_app(tmp_path: Path):
    f = _write(tmp_path / "other.py", "import sys\nprint('hi')\n")
    assert not is_marimo_app(str(f))


def test_markdown_app_detected(tmp_path: Path):
    f = _write(tmp_path / "notebook.md", MARIMO_MD)
    assert is_marimo_app(str(f))


def test_markdown_app_detected_with_long_frontmatter(tmp_path: Path):
    """Long YAML frontmatter must not hide the marimo-version marker."""
    padding = "\n".join(f"key{i}: value{i}" for i in range(50))
    content = f"---\n{padding}\nmarimo-version: 0.1.0\n---\n"
    assert len(content.encode()) > 512  # ensure we exercise the slow path
    f = _write(tmp_path / "notebook.md", content)
    assert is_marimo_app(str(f))


def test_python_app_detected_with_long_docstring(tmp_path: Path):
    """Long module docstrings must not hide marimo markers (issue #9647)."""
    f = _write(tmp_path / "app.py", f'"""{"x" * 1024}"""\n' + MARIMO_APP)
    assert is_marimo_app(str(f))


def test_python_app_detected_with_script_header(tmp_path: Path):
    """PEP 723 script headers larger than the fast-path window are still detected."""
    padding = "# " + ("x" * 80) + "\n"
    header = "# /// script\n" + (padding * 10) + "# ///\n"
    f = _write(tmp_path / "app.py", header + MARIMO_APP)
    assert is_marimo_app(str(f))


def test_python_non_app_with_long_content(tmp_path: Path):
    """Slow-path scan still rejects non-marimo Python files."""
    content = '"""' + ("x" * 1024) + '"""\nimport sys\nprint("hi")\n'
    f = _write(tmp_path / "other.py", content)
    assert not is_marimo_app(str(f))


@pytest.fixture
def test_dir(tmp_path: Path) -> Path:
    """Fixture dir: two marimo apps, a markdown notebook, and a nested app."""
    _write(tmp_path / "app1.py", MARIMO_APP)
    _write(tmp_path / "app2.py", MARIMO_APP)
    _write(tmp_path / "notebook.md", MARIMO_MD)
    nested = tmp_path / "nested"
    nested.mkdir()
    _write(nested / "nested_app.py", MARIMO_APP)
    return tmp_path


class TestDirectoryScanner:
    def test_basic_scan(self, test_dir: Path):
        files = DirectoryScanner(str(test_dir)).scan()
        assert set(_file_names(files)) == {"app1.py", "app2.py"}

    def test_scan_with_markdown(self, test_dir: Path):
        files = DirectoryScanner(str(test_dir), include_markdown=True).scan()
        assert set(_file_names(files)) == {
            "app1.py",
            "app2.py",
            "notebook.md",
        }

    def test_scan_nested_directories(self, test_dir: Path):
        files = DirectoryScanner(str(test_dir)).scan()
        nested = next(
            f for f in files if f.is_directory and f.name == "nested"
        )
        assert nested.children is not None
        assert nested.children[0].name == "nested_app.py"

    def test_max_files_limit(self, test_dir: Path):
        for i in range(10):
            _write(test_dir / f"app{i + 3}.py", MARIMO_APP)
        files = DirectoryScanner(str(test_dir), max_files=5).scan()
        assert _count_files(files) == 5

    def test_max_files_limit_recursion_at_boundary(
        self, test_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A subdir recursion that reaches max_files must not let another
        top-level file slip in. Forces the ordering that only flaked in CI."""
        import marimo._server.files.directory_scanner as scanner_mod

        for i in range(10):
            _write(test_dir / f"app{i + 3}.py", MARIMO_APP)

        real_scandir = os.scandir

        def ordered_scandir(path: str):  # type: ignore[no-untyped-def]
            entries = list(real_scandir(path))
            dirs = [e for e in entries if e.is_dir()]
            files = sorted(
                (e for e in entries if not e.is_dir()), key=lambda e: e.name
            )
            # 4 files, then the nested dir (reaches the limit), then the rest.
            return files[:4] + dirs + files[4:]

        monkeypatch.setattr(scanner_mod.os, "scandir", ordered_scandir)
        files = DirectoryScanner(str(test_dir), max_files=5).scan()
        assert _count_files(files) == 5

    def test_skip_common_directories(self, test_dir: Path):
        skip_names = (
            "venv",
            "node_modules",
            "__pycache__",
            ".git",
            "winpython",
        )
        for name in skip_names:
            d = test_dir / name
            d.mkdir()
            _write(d / "app.py", MARIMO_APP)
        scanner = DirectoryScanner(str(test_dir))
        scanner.scan()
        # Skipped dirs must not contribute marimo files anywhere in the tree.
        for f in scanner.partial_results:
            for name in skip_names:
                assert name not in f.path

    def test_skip_common_directories_case_insensitive(self, test_dir: Path):
        """WinPython distributions often vary case."""
        d = test_dir / "WinPython"
        d.mkdir()
        _write(d / "app.py", MARIMO_APP)
        files = DirectoryScanner(str(test_dir)).scan()
        for f in files:
            assert "winpython" not in f.path.lower()

    def test_skip_hidden_files(self, test_dir: Path):
        _write(test_dir / ".hidden_app.py", MARIMO_APP)
        files = DirectoryScanner(str(test_dir)).scan()
        assert ".hidden_app.py" not in _file_names(files)

    def test_skip_symlinks(self, test_dir: Path):
        """Broken links, cycles, and valid links are all skipped."""
        try:
            os.symlink(
                test_dir / "nonexistent.py", test_dir / "broken_link.py"
            )
            os.symlink(test_dir, test_dir / "cycle", target_is_directory=True)
            os.symlink(test_dir / "app1.py", test_dir / "linked_app.py")
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")

        files = DirectoryScanner(str(test_dir)).scan()
        names = _file_names(files)
        dir_names = [f.name for f in files if f.is_directory]

        assert "broken_link.py" not in names
        assert "linked_app.py" not in names
        assert "cycle" not in dir_names
        assert "app1.py" in names
        assert "app2.py" in names

    def test_scan_includes_notebook_with_long_docstring(self, test_dir: Path):
        """Folder scans surface notebooks with long docstrings (issue #9647)."""
        _write(
            test_dir / "long_docstring_app.py",
            f'"""{"x" * 1024}"""\n' + MARIMO_APP,
        )
        files = DirectoryScanner(str(test_dir)).scan()
        assert "long_docstring_app.py" in _file_names(files)

    def test_partial_results_populated_during_scan(self, test_dir: Path):
        scanner = DirectoryScanner(str(test_dir))
        assert scanner.partial_results == []
        scanner.scan()
        assert len(scanner.partial_results) >= 2
        for f in scanner.partial_results:
            assert not f.is_directory
            assert f.is_marimo_file


# --- ipynb detection and discovery tests ---

MARIMO_IPYNB = """\
{
 "cells": [],
 "metadata": {"marimo": {"marimo_version": "0.1.0"}},
 "nbformat": 4,
 "nbformat_minor": 5
}"""

PLAIN_IPYNB = """\
{
 "cells": [{"cell_type": "code","source": ["x=1"],"metadata": {}}],
 "metadata": {"kernelspec": {"display_name":"Python 3","language":"python","name":"python3"}},
 "nbformat": 4,
 "nbformat_minor": 5
}"""


def test_ipynb_marimo_app_detected(tmp_path: Path):
    f = _write(tmp_path / "notebook.ipynb", MARIMO_IPYNB)
    assert is_marimo_app(str(f)) is True


def test_ipynb_non_marimo_app(tmp_path: Path):
    f = _write(tmp_path / "plain.ipynb", PLAIN_IPYNB)
    assert is_marimo_app(str(f)) is False


def test_ipynb_app_detected_os_filesystem(tmp_path: Path):
    """os_file_system._is_marimo_file also delegates to is_marimo_app."""
    from marimo._server.files.os_file_system import OSFileSystem

    fs = OSFileSystem()
    f = _write(tmp_path / "marimo.ipynb", MARIMO_IPYNB)
    info = fs._get_file_info(str(f))
    assert info.is_marimo_file is True


def test_ipynb_non_app_os_filesystem(tmp_path: Path):
    """Non-marimo ipynb files are not flagged by os_file_system."""
    from marimo._server.files.os_file_system import OSFileSystem

    fs = OSFileSystem()
    f = _write(tmp_path / "plain.ipynb", PLAIN_IPYNB)
    info = fs._get_file_info(str(f))
    assert info.is_marimo_file is False


@pytest.fixture
def test_dir_with_ipynb(tmp_path: Path) -> Path:
    """Fixture dir with python apps, markdown notebook, and ipynb notebooks."""
    _write(tmp_path / "app1.py", MARIMO_APP)
    _write(tmp_path / "app2.py", MARIMO_APP)
    _write(tmp_path / "notebook.md", MARIMO_MD)
    _write(tmp_path / "marimo.ipynb", MARIMO_IPYNB)
    _write(tmp_path / "plain.ipynb", PLAIN_IPYNB)  # should NOT be discovered
    nested = tmp_path / "nested"
    nested.mkdir()
    _write(nested / "nested_app.py", MARIMO_APP)
    return tmp_path


class TestDirectoryScannerIpynb:
    def test_ipynb_discovered_in_default_scan(self, test_dir_with_ipynb: Path):
        """ipynb files are found by default (without include_markdown)."""
        files = DirectoryScanner(str(test_dir_with_ipynb)).scan()
        names = _file_names(files)
        assert "marimo.ipynb" in names
        assert "app1.py" in names
        assert "app2.py" in names
        # Plain ipynb (no marimo metadata) should NOT be discovered
        assert "plain.ipynb" not in names

    def test_ipynb_not_in_markdown_mode(self, test_dir_with_ipynb: Path):
        """include_markdown=True should not exclude ipynb files."""
        files = DirectoryScanner(
            str(test_dir_with_ipynb), include_markdown=True
        ).scan()
        names = _file_names(files)
        assert "marimo.ipynb" in names
        assert "notebook.md" in names
        assert "app1.py" in names
        assert "app2.py" in names

    def test_ipynb_in_nested_directory(self, test_dir_with_ipynb: Path):
        """Nested ipynb files should be discovered."""
        nested_ipynb = test_dir_with_ipynb / "nested" / "deep.ipynb"
        _write(nested_ipynb, MARIMO_IPYNB)
        files = DirectoryScanner(str(test_dir_with_ipynb)).scan()
        nested = next(
            f for f in files if f.is_directory and f.name == "nested"
        )
        assert nested.children is not None
        names = [c.name for c in nested.children]
        assert "deep.ipynb" in names
