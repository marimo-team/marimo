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

    def test_max_depth_omits_deeper_notebooks(self, tmp_path: Path) -> None:
        """Notebooks beyond max_depth are silently dropped (issue #10064).

        Home-page workspace scans use DirectoryScanner with a shallow default
        depth. When users open marimo from a broad root (e.g. $HOME), deeper
        project notebooks vanish from the tree without warning.
        """
        # root /
        #   shallow_app.py          (depth 0 file — always included)
        #   d1/
        #     mid_app.py            (depth 1 file — included when max_depth>=1)
        #     d2/
        #       deep_app.py         (depth 2 file — omitted when max_depth=1)
        _write(tmp_path / "shallow_app.py", MARIMO_APP)
        d1 = tmp_path / "d1"
        d1.mkdir()
        _write(d1 / "mid_app.py", MARIMO_APP)
        d2 = d1 / "d2"
        d2.mkdir()
        _write(d2 / "deep_app.py", MARIMO_APP)

        files = DirectoryScanner(str(tmp_path), max_depth=1).scan()
        names = set(_file_names(files))
        assert "shallow_app.py" in names
        # nested folder at depth 0 should still appear with its mid app
        nested = next(f for f in files if f.is_directory and f.name == "d1")
        assert nested.children is not None
        nested_names = {c.name for c in nested.children}
        assert "mid_app.py" in nested_names
        # depth-2 notebook must not appear anywhere
        assert "deep_app.py" not in nested_names
        assert "deep_app.py" not in names
        assert "d2" not in nested_names

    def test_max_depth_includes_notebook_at_limit(
        self, tmp_path: Path
    ) -> None:
        """A notebook whose enclosing folder is at max_depth is still found."""
        # root/d1/d2/app.py with max_depth=2 → d2 is entered at depth=1 < 2?
        # recurse(dir, depth): folder children requested via recurse(path, depth+1)
        # At folder d1 (depth of recurse for d1 is 1 when called from root depth 0+1).
        # When depth==max_depth, subdirs are skipped (not entered).
        # Files in the current directory are still collected when depth <= max_depth.
        #
        # Tree:
        #   L1/app.py   — collected while recurse(L1) runs at depth=1, max_depth=1
        #   L1/L2/app.py — L2 skipped because depth==max_depth when visiting L1
        L1 = tmp_path / "L1"
        L1.mkdir()
        _write(L1 / "at_limit_app.py", MARIMO_APP)
        L2 = L1 / "L2"
        L2.mkdir()
        _write(L2 / "beyond_app.py", MARIMO_APP)

        files = DirectoryScanner(str(tmp_path), max_depth=1).scan()
        # Collect all file names recursively

        def all_names(nodes: list[FileInfo]) -> set[str]:
            out: set[str] = set()
            for n in nodes:
                if n.is_directory:
                    out |= all_names(n.children or [])
                else:
                    out.add(n.name)
            return out

        found = all_names(files)
        assert "at_limit_app.py" in found
        assert "beyond_app.py" not in found
