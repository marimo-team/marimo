# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest

from marimo import _loggers
from marimo._save.cache_dirs import (
    NotANotebookError,
    directory_cache_dir,
    notebook_cache_dir,
    resolve_cache_dirs,
)

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


def write_notebook(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(NOTEBOOK)
    return path


def make_cache_dir(root: Path, *parts: str) -> Path:
    cache_dir = root.joinpath(*parts, "__marimo__", "cache")
    cache_dir.mkdir(parents=True)
    return cache_dir


def test_resolve_directory_takes_its_own_cache_dir(tmp_path: Path) -> None:
    # Nested caches belong to their own directories, not to this one.
    make_cache_dir(tmp_path, "a")
    own = make_cache_dir(tmp_path)

    assert resolve_cache_dirs(tmp_path) == [own]


def test_resolve_directory_lists_its_cache_dir_before_it_exists(
    tmp_path: Path,
) -> None:
    resolved = resolve_cache_dirs(tmp_path)

    assert resolved == [tmp_path / "__marimo__" / "cache"]
    assert not resolved[0].exists()


def test_resolve_recursive_finds_nested_cache_dirs(tmp_path: Path) -> None:
    nested = make_cache_dir(tmp_path, "b", "deeper")
    top = make_cache_dir(tmp_path, "a")
    # A __marimo__ directory without a cache directory is not a hit.
    tmp_path.joinpath("c", "__marimo__").mkdir(parents=True)

    assert resolve_cache_dirs(tmp_path, recursive=True) == [top, nested]


def test_resolve_recursive_skips_dot_folders(tmp_path: Path) -> None:
    make_cache_dir(tmp_path, ".venv", "lib")
    kept = make_cache_dir(tmp_path, "notebooks")

    assert resolve_cache_dirs(tmp_path, recursive=True) == [kept]


def test_resolve_recursive_dot_folder_given_explicitly(tmp_path: Path) -> None:
    hidden = make_cache_dir(tmp_path, ".hidden")

    assert resolve_cache_dirs(tmp_path / ".hidden", recursive=True) == [hidden]


def test_resolve_recursive_directory_without_caches(tmp_path: Path) -> None:
    assert resolve_cache_dirs(tmp_path, recursive=True) == []


@pytest.mark.parametrize("recursive", [False, True])
def test_resolve_a_cache_directory_itself(
    tmp_path: Path, recursive: bool
) -> None:
    # A resolved directory has to resolve to itself, so that a path printed by
    # `marimo cache dir` can be handed back to another cache command.
    cache_dir = make_cache_dir(tmp_path, "notebooks")

    assert resolve_cache_dirs(cache_dir, recursive=recursive) == [cache_dir]


@pytest.mark.parametrize("recursive", [False, True])
def test_resolve_an_ordinary_directory_named_cache(
    tmp_path: Path, recursive: bool
) -> None:
    # Only a "cache" directory under __marimo__ is a cache directory. One a
    # project happens to name "cache" owns a cache directory like any other.
    plain = tmp_path / "cache"
    own = make_cache_dir(plain)

    assert resolve_cache_dirs(plain, recursive=recursive) == [own]


def test_resolve_recursive_marimo_directory_itself(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path, "notebooks")

    assert resolve_cache_dirs(cache_dir.parent, recursive=True) == [cache_dir]


def test_resolve_relative_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert resolve_cache_dirs(Path(".")) == [
        Path.cwd() / "__marimo__" / "cache"
    ]


def test_resolve_recursive_relative_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_cache_dir(tmp_path, "notebooks")
    monkeypatch.chdir(tmp_path)

    assert resolve_cache_dirs(Path("."), recursive=True) == [
        Path.cwd() / "notebooks" / "__marimo__" / "cache"
    ]


def test_resolve_relative_cache_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = make_cache_dir(tmp_path, "notebooks")
    monkeypatch.chdir(cache_dir)

    assert resolve_cache_dirs(Path(".")) == [Path.cwd()]


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not restrict reads on Windows"
)
def test_resolve_recursive_warns_about_an_unreadable_subtree(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unreadable = tmp_path / "locked"
    unreadable.mkdir()
    unreadable.chmod(0o000)
    if os.access(unreadable, os.R_OK):  # running as root
        unreadable.chmod(0o755)
        pytest.skip("chmod does not restrict reads for this user")
    monkeypatch.setattr(_loggers.marimo_logger(), "propagate", True)

    try:
        with caplog.at_level(logging.WARNING):
            assert resolve_cache_dirs(tmp_path, recursive=True) == []
    finally:
        unreadable.chmod(0o755)

    assert str(unreadable) in caplog.text


def test_resolve_notebook_lists_its_dir_before_it_exists(
    tmp_path: Path,
) -> None:
    notebook = write_notebook(tmp_path / "nb.py")

    resolved = resolve_cache_dirs(notebook)

    assert resolved == [tmp_path / "__marimo__" / "cache"]
    assert not resolved[0].exists()


def test_resolve_notebook_relative_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_notebook(tmp_path / "nb.py")
    monkeypatch.chdir(tmp_path)

    assert resolve_cache_dirs(Path("nb.py")) == [
        Path.cwd() / "__marimo__" / "cache"
    ]


def test_resolve_notebook_honors_pycache_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = tmp_path / "pycache"
    monkeypatch.setattr(sys, "pycache_prefix", str(prefix))
    notebook = write_notebook(tmp_path / "notebooks" / "nb.py")

    expected = prefix.joinpath(
        *notebook.parent.parts[1:], "__marimo__", "cache"
    )
    assert resolve_cache_dirs(notebook) == [expected]
    assert notebook_cache_dir(notebook) == expected


def test_resolve_directory_honors_pycache_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Under a prefix a notebook's cache lives in the mirrored tree, so a
    # directory has to report the same directory the notebook does.
    prefix = tmp_path / "pycache"
    monkeypatch.setattr(sys, "pycache_prefix", str(prefix))
    notebook = write_notebook(tmp_path / "notebooks" / "nb.py")
    mirrored = prefix.joinpath(
        *notebook.parent.parts[1:], "__marimo__", "cache"
    )

    assert resolve_cache_dirs(notebook.parent) == [mirrored]
    assert resolve_cache_dirs(notebook) == [mirrored]


def test_directory_cache_dir_for_a_directory_that_does_not_exist(
    tmp_path: Path,
) -> None:
    # A suffix makes a name look like a file, and a directory that is still to
    # be created cannot be told apart from one by asking the filesystem.
    absent = tmp_path / "data.v2"

    assert directory_cache_dir(absent) == absent / "__marimo__" / "cache"


def test_resolve_recursive_honors_pycache_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = tmp_path / "pycache"
    monkeypatch.setattr(sys, "pycache_prefix", str(prefix))
    notebook = write_notebook(tmp_path / "notebooks" / "nb.py")
    mirrored = prefix.joinpath(
        *notebook.parent.parts[1:], "__marimo__", "cache"
    )
    mirrored.mkdir(parents=True)

    assert resolve_cache_dirs(notebook.parent, recursive=True) == [mirrored]


def test_resolve_rejects_plain_python_script(tmp_path: Path) -> None:
    script = tmp_path / "script.py"
    script.write_text("print('hello')\n")

    with pytest.raises(NotANotebookError):
        resolve_cache_dirs(script)


def test_resolve_rejects_empty_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.py"
    empty.write_text("")

    with pytest.raises(NotANotebookError):
        resolve_cache_dirs(empty)


def test_resolve_rejects_unsupported_file_type(tmp_path: Path) -> None:
    data = tmp_path / "data.csv"
    data.write_text("a,b\n1,2\n")

    with pytest.raises(NotANotebookError):
        resolve_cache_dirs(data)


def test_resolve_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_cache_dirs(tmp_path / "absent.py")


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs named pipes")
def test_resolve_rejects_a_file_that_cannot_be_read_as_text(
    tmp_path: Path,
) -> None:
    # Reading a pipe with no writer never returns, so it is refused unread.
    pipe = tmp_path / "pipe.py"
    os.mkfifo(pipe)

    with pytest.raises(NotANotebookError, match="not a notebook file"):
        resolve_cache_dirs(pipe)
