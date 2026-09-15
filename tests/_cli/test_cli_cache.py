# Copyright 2026 Marimo. All rights reserved.
"""CLI tests for the marimo cache command group."""

from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner

from marimo._cli.cache.commands import cache
from marimo._cli.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

NOTEBOOK = """
import marimo

app = marimo.App()


@app.cell
def _():
    x = 1
    return (x,)


if __name__ == "__main__":
    app.run()
"""


def make_cache_dir(root: Path, *parts: str) -> Path:
    cache_dir = root.joinpath(*parts, "__marimo__", "cache")
    cache_dir.mkdir(parents=True)
    return cache_dir


def test_cache_group_is_registered_and_documented() -> None:
    # A hidden group drops out of `marimo --help` and out of the generated
    # CLI documentation.
    assert main.commands["cache"] is cache
    assert not cache.hidden


def test_dir_prints_the_directorys_own_cache_directory(tmp_path: Path) -> None:
    own = make_cache_dir(tmp_path)
    make_cache_dir(tmp_path, "nested")

    result = CliRunner().invoke(main, ["cache", "dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [str(own)]


def test_dir_recursive_prints_every_cache_directory(tmp_path: Path) -> None:
    first = make_cache_dir(tmp_path, "a")
    second = make_cache_dir(tmp_path, "b", "deeper")

    result = CliRunner().invoke(main, ["cache", "dir", "-r", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [str(first), str(second)]


def test_dir_defaults_to_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = make_cache_dir(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(main, ["cache", "dir"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [str(cache_dir)]


def test_dir_marks_a_cache_directory_that_does_not_exist(
    tmp_path: Path,
) -> None:
    result = CliRunner().invoke(main, ["cache", "dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    expected = tmp_path / "__marimo__" / "cache"
    assert result.output == f"{expected} (does not exist)\n"


def test_dir_recursive_reports_no_cache_directories(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main, ["cache", "dir", "--recursive", str(tmp_path)]
    )

    assert result.exit_code == 0, result.output
    assert result.output == "No cache directories found.\n"


def test_dir_notebook_path(tmp_path: Path) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = tmp_path / "__marimo__" / "cache"
    cache_dir.mkdir(parents=True)

    result = CliRunner().invoke(main, ["cache", "dir", str(notebook)])

    assert result.exit_code == 0, result.output
    assert result.output == f"{cache_dir}\n"


def test_dir_recursive_notebook_path(tmp_path: Path) -> None:
    # A notebook names one cache directory, so there is nothing to search and
    # -r neither errors nor changes the answer.
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    make_cache_dir(tmp_path, "nested")

    result = CliRunner().invoke(main, ["cache", "dir", "-r", str(notebook)])

    assert result.exit_code == 0, result.output
    assert result.output == f"{cache_dir}\n"


def test_dir_notebook_without_a_cache_directory(tmp_path: Path) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)

    result = CliRunner().invoke(main, ["cache", "dir", str(notebook)])

    assert result.exit_code == 0, result.output
    expected = tmp_path / "__marimo__" / "cache"
    assert result.output == f"{expected} (does not exist)\n"


def test_dir_rejects_a_file_that_is_not_a_notebook(tmp_path: Path) -> None:
    script = tmp_path / "script.py"
    script.write_text("print('hello')\n")

    result = CliRunner().invoke(main, ["cache", "dir", str(script)])

    assert result.exit_code == 1
    assert "is not a marimo notebook" in result.stderr


def test_dir_rejects_a_missing_path(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main, ["cache", "dir", str(tmp_path / "absent")]
    )

    assert result.exit_code == 2
    assert "does not exist" in result.stderr
