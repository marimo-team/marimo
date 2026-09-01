# Copyright 2026 Marimo. All rights reserved.
"""CLI tests for the marimo cache command group."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from marimo._cli.cache.commands import cache, format_bytes
from marimo._cli.cli import main

if TYPE_CHECKING:
    from pathlib import Path

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


def test_dir_marks_a_file_in_the_way_of_the_cache_directory(
    tmp_path: Path,
) -> None:
    (tmp_path / "__marimo__").mkdir()
    blocker = tmp_path / "__marimo__" / "cache"
    blocker.write_text("")

    result = CliRunner().invoke(main, ["cache", "dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output == f"{blocker} (not a directory)\n"


def write_entry(cache_dir: Path, block: str, name: str, size: int) -> None:
    entry = cache_dir / block / name
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_bytes(b"x" * size)


@pytest.mark.parametrize(
    ("size", "rendered"),
    [
        (0, "0 B"),
        (512, "512 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        # A byte short of the next unit rounds up to it, never to "1024.0".
        (1024**2 - 1, "1.0 MB"),
        (1024**3 - 1, "1.0 GB"),
        (3 * 1024 * 1024, "3.0 MB"),
        (1024**5, "1.0 PB"),
        # Nothing bigger than a petabyte to fall back on.
        (2 * 1024**6, "2048.0 PB"),
    ],
)
def test_format_bytes(size: int, rendered: str) -> None:
    assert format_bytes(size) == rendered


def test_size_reports_each_directory_and_a_total(tmp_path: Path) -> None:
    first = make_cache_dir(tmp_path, "a")
    write_entry(first, "train", "C_ab12.pickle", 2048)
    second = make_cache_dir(tmp_path, "b")
    write_entry(second, "train", "C_77e0.pickle", 1024)
    write_entry(second, "train", "E_9f00.pickle", 1024)

    result = CliRunner().invoke(main, ["cache", "size", "-r", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{first}\t2.0 KB\t1 entry",
        f"{second}\t2.0 KB\t2 entries",
        "Total\t4.0 KB\t3 entries",
    ]


def test_size_of_a_single_directory_omits_the_total(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 10)

    result = CliRunner().invoke(main, ["cache", "size", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [f"{cache_dir}\t10 B\t1 entry"]


def test_size_of_a_cache_directory_that_does_not_exist(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["cache", "size", str(tmp_path)])

    assert result.exit_code == 0, result.output
    expected = tmp_path / "__marimo__" / "cache"
    assert result.output == f"{expected} (does not exist)\t0 B\t0 entries\n"


def test_size_of_a_notebook_path(tmp_path: Path) -> None:
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK)
    cache_dir = make_cache_dir(tmp_path)
    write_entry(cache_dir, "train", "C_ab12.pickle", 4)

    result = CliRunner().invoke(main, ["cache", "size", str(notebook)])

    assert result.exit_code == 0, result.output
    assert result.output == f"{cache_dir}\t4 B\t1 entry\n"


def test_size_recursive_reports_no_cache_directories(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["cache", "size", "-r", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert result.output == "No cache directories found.\n"
