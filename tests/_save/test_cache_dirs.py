# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest

from marimo import _loggers
from marimo._save.cache_dirs import (
    CacheDirStats,
    NotANotebookError,
    block_dir_name,
    cache_dir_stats,
    clean_cache_dir,
    delete_cache_entries,
    directory_cache_dir,
    entry_bytes,
    notebook_cache_dir,
    partial_write_name,
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


def populate_cache_dir(cache_dir: Path) -> None:
    """Write a cache directory in the shape the loaders leave behind."""
    block = cache_dir / "train"
    block.mkdir(parents=True)
    (block / "C_ab12.pickle").write_bytes(b"x" * 10)
    (block / "E_9f00.pickle").write_bytes(b"y" * 20)
    # A lazily loaded value is split over a directory of blobs, named after
    # the hash its entry file also names.
    blob = block / "ab12"
    blob.mkdir()
    (blob / "return.npy").write_bytes(b"z" * 30)
    (blob / "meta.json").write_bytes(b"w" * 40)
    (cache_dir / ".nb-export.json").write_bytes(b"m" * 5)


def test_cache_dir_stats_counts_an_entry_and_its_blobs_once(
    tmp_path: Path,
) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)

    assert cache_dir_stats(cache_dir) == CacheDirStats(
        total_bytes=105, entries=2
    )


def test_cache_dir_stats_does_not_count_an_interrupted_write(
    tmp_path: Path,
) -> None:
    """A killed kernel leaves the sibling of a rename. It is not an entry."""
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)
    leftover = cache_dir / "train" / partial_write_name("C_77e0.pickle")
    leftover.write_bytes(b"p" * 8)

    # The bytes are on disk and reported as such. The value is not.
    assert cache_dir_stats(cache_dir) == CacheDirStats(
        total_bytes=113, entries=2
    )


def test_cache_dir_stats_counts_an_orphaned_blob_directory(
    tmp_path: Path,
) -> None:
    # Nothing names the hash, so the blobs are all that is left of the value.
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)
    (cache_dir / "train" / "C_ab12.pickle").unlink()

    assert cache_dir_stats(cache_dir) == CacheDirStats(
        total_bytes=95, entries=2
    )


def test_cache_dir_stats_counts_several_blocks(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)
    other = cache_dir / "evaluate"
    other.mkdir()
    (other / "C_77e0.pickle").write_bytes(b"x" * 7)

    assert cache_dir_stats(cache_dir) == CacheDirStats(
        total_bytes=112, entries=3
    )


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not restrict reads on Windows"
)
def test_cache_dir_stats_skips_an_unreadable_block(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)
    unreadable = cache_dir / "locked"
    unreadable.mkdir()
    (unreadable / "C_77e0.pickle").write_bytes(b"x" * 7)
    unreadable.chmod(0o000)
    if os.access(unreadable, os.R_OK):  # running as root
        unreadable.chmod(0o755)
        pytest.skip("chmod does not restrict reads for this user")
    monkeypatch.setattr(_loggers.marimo_logger(), "propagate", True)

    try:
        with caplog.at_level(logging.WARNING):
            stats = cache_dir_stats(cache_dir)
    finally:
        unreadable.chmod(0o755)

    assert stats == CacheDirStats(total_bytes=105, entries=2)
    assert str(unreadable) in caplog.text


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlinks need a privileged user"
)
def test_cache_dir_stats_counts_a_symlink_as_itself(tmp_path: Path) -> None:
    # Deleting the cache would not free what the link points at.
    outside = tmp_path / "checkpoint.bin"
    outside.write_bytes(b"x" * 4096)
    cache_dir = make_cache_dir(tmp_path)
    block = cache_dir / "train"
    block.mkdir()
    link = block / "C_ab12.pickle"
    link.symlink_to(outside)

    stats = cache_dir_stats(cache_dir)

    assert stats.entries == 1
    assert stats.total_bytes == link.lstat().st_size
    assert stats.total_bytes < 4096


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlinks need a privileged user"
)
def test_cache_dir_stats_does_not_walk_a_linked_block(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "C_ab12.pickle").write_bytes(b"x" * 4096)
    cache_dir = make_cache_dir(tmp_path)
    (cache_dir / "train").symlink_to(outside, target_is_directory=True)

    stats = cache_dir_stats(cache_dir)

    assert stats.entries == 0
    assert stats.total_bytes < 4096


def test_cache_dir_stats_of_an_empty_directory(tmp_path: Path) -> None:
    assert cache_dir_stats(make_cache_dir(tmp_path)) == CacheDirStats()


def test_cache_dir_stats_of_a_directory_that_does_not_exist(
    tmp_path: Path,
) -> None:
    assert cache_dir_stats(tmp_path / "absent") == CacheDirStats()


def test_cache_dir_stats_add() -> None:
    left = CacheDirStats(total_bytes=10, entries=1)
    right = CacheDirStats(total_bytes=5, entries=2)

    assert left + right == CacheDirStats(total_bytes=15, entries=3)


def test_cache_dir_stats_subtract() -> None:
    left = CacheDirStats(total_bytes=10, entries=3)
    right = CacheDirStats(total_bytes=4, entries=1)

    assert left - right == CacheDirStats(total_bytes=6, entries=2)
    # A cache holding less than nothing has no meaning to report.
    assert right - left == CacheDirStats()


def test_entry_bytes(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)

    assert entry_bytes(cache_dir / "train") == 100
    assert entry_bytes(cache_dir / "train" / "ab12") == 70
    assert entry_bytes(cache_dir / "train" / "C_ab12.pickle") == 10
    assert entry_bytes(cache_dir / "never-written") == 0


def populate_lazy_block(cache_dir: Path, block_name: str = "train") -> Path:
    """Write a block in the shape a lazily written value leaves behind."""
    block = cache_dir / block_name
    for entry_hash, size in (("ab12", 20), ("77e0", 40)):
        blobs = block / entry_hash
        blobs.mkdir(parents=True)
        (blobs / "return.pickle").write_bytes(b"y" * size)
        (block / f"C_{entry_hash}.jsonl").write_bytes(b"x" * 10)
    return block


def test_block_dir_name_replaces_what_a_path_cannot_hold() -> None:
    assert block_dir_name("train") == "train"
    assert block_dir_name("train/v2") == "train_v2"
    assert block_dir_name("épochs") == "_pochs"


def test_clean_removes_every_block_and_its_blobs(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)
    populate_lazy_block(cache_dir, "evaluate")

    freed = clean_cache_dir(cache_dir)

    assert freed == CacheDirStats(total_bytes=180, entries=4)
    # The manifests describing the cache outlive the entries they describe.
    assert [path.name for path in cache_dir.iterdir()] == [".nb-export.json"]


def test_clean_keeps_the_blocks_it_was_not_named(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)
    populate_lazy_block(cache_dir, "evaluate")

    freed = clean_cache_dir(cache_dir, ["evaluate"])

    assert freed == CacheDirStats(total_bytes=80, entries=2)
    assert not (cache_dir / "evaluate").exists()
    assert cache_dir_stats(cache_dir) == CacheDirStats(
        total_bytes=105, entries=2
    )


def test_clean_matches_a_name_as_it_is_written_to_disk(
    tmp_path: Path,
) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_lazy_block(cache_dir, "train_v2")

    assert clean_cache_dir(cache_dir, ["train/v2"]).entries == 2


def test_clean_of_a_name_no_block_answers_to(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)

    assert clean_cache_dir(cache_dir, ["absent"]) == CacheDirStats()
    assert cache_dir_stats(cache_dir) == CacheDirStats(
        total_bytes=105, entries=2
    )


def test_clean_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)

    planned = clean_cache_dir(cache_dir, dry_run=True)

    assert planned == CacheDirStats(total_bytes=100, entries=2)
    assert clean_cache_dir(cache_dir) == planned


def test_clean_of_a_directory_that_does_not_exist(tmp_path: Path) -> None:
    assert clean_cache_dir(tmp_path / "absent") == CacheDirStats()


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not restrict writes on Windows"
)
def test_clean_reports_only_what_a_block_gave_up(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bytes a block did not give up are not reported as freed."""
    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)
    kept = block / "ab12"
    kept.chmod(0o555)
    if os.access(kept, os.W_OK):  # running as root
        kept.chmod(0o755)
        pytest.skip("chmod does not restrict writes for this user")
    monkeypatch.setattr(_loggers.marimo_logger(), "propagate", True)

    try:
        with caplog.at_level(logging.WARNING):
            freed = clean_cache_dir(cache_dir)
    finally:
        kept.chmod(0o755)

    assert freed == CacheDirStats(total_bytes=60, entries=1)
    assert (kept / "return.pickle").read_bytes() == b"y" * 20
    assert str(block) in caplog.text


def test_delete_entries_takes_the_blobs_of_the_entry(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)

    freed = delete_cache_entries(cache_dir, [("train", "C_ab12")])

    assert freed == CacheDirStats(total_bytes=30, entries=1)
    assert not (block / "ab12").exists()
    assert sorted(path.name for path in block.iterdir()) == [
        "77e0",
        "C_77e0.jsonl",
    ]


def test_delete_entries_keeps_blobs_another_entry_can_read(
    tmp_path: Path,
) -> None:
    # One value serves both entries, and only one of them is deleted.
    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)
    (block / "E_ab12.jsonl").write_bytes(b"x" * 10)

    freed = delete_cache_entries(cache_dir, [("train", "C_ab12")])

    assert freed == CacheDirStats(total_bytes=10, entries=1)
    assert (block / "ab12" / "return.pickle").exists()


def test_delete_entries_takes_shared_blobs_once(tmp_path: Path) -> None:
    # Both entries reading one value are deleted, so the value goes with them.
    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)
    (block / "E_ab12.jsonl").write_bytes(b"x" * 10)
    entries = [("train", "C_ab12"), ("train", "E_ab12")]

    planned = delete_cache_entries(cache_dir, entries, dry_run=True)

    # Blobs the two entries share are freed once, whether counted or removed.
    assert planned == CacheDirStats(total_bytes=40, entries=2)
    assert delete_cache_entries(cache_dir, entries) == planned
    assert not (block / "ab12").exists()


def test_delete_entries_refuses_a_name_that_leaves_the_cache(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A manifest is a file like any other. What it names must be an entry."""
    outside = tmp_path / "model.bin"
    outside.write_bytes(b"o" * 40)
    cache_dir = make_cache_dir(tmp_path)
    populate_lazy_block(cache_dir)
    monkeypatch.setattr(_loggers.marimo_logger(), "propagate", True)

    with caplog.at_level(logging.WARNING):
        freed = delete_cache_entries(
            cache_dir,
            [
                ("../..", "model"),
                ("train", ".."),
                ("train", "../../model"),
                # A separator is outside the key's character set, so no key
                # can name a parent, however its hash would read.
                ("train", "C_.."),
                # Without a type prefix a key would name a directory of blobs.
                ("train", "ab12"),
            ],
        )

    assert freed == CacheDirStats()
    assert outside.exists()
    assert cache_dir.is_dir()
    assert cache_dir_stats(cache_dir) == CacheDirStats(
        total_bytes=80, entries=2
    )
    assert "no cache entry can be named that" in caplog.text


def test_delete_entries_removes_a_marker_before_the_blobs_it_covers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Half an entry must never be readable: the marker goes first."""
    from marimo._save import cache_dirs

    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)
    marker_gone: list[bool] = []
    remove_tree = cache_dirs._remove_tree

    def spy(directory: Path) -> int:
        marker_gone.append(not (block / "C_ab12.jsonl").exists())
        return remove_tree(directory)

    monkeypatch.setattr(cache_dirs, "_remove_tree", spy)
    delete_cache_entries(cache_dir, [("train", "C_ab12")])

    assert marker_gone == [True]


def test_delete_entries_takes_the_leftovers_of_a_killed_write(
    tmp_path: Path,
) -> None:
    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)
    leftover = block / partial_write_name("C_ab12.jsonl")
    leftover.write_bytes(b"p" * 8)

    freed = delete_cache_entries(cache_dir, [("train", "C_ab12")])

    assert freed == CacheDirStats(total_bytes=38, entries=1)
    assert not leftover.exists()


def test_delete_entries_of_an_entry_the_cache_no_longer_holds(
    tmp_path: Path,
) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_lazy_block(cache_dir)

    freed = delete_cache_entries(
        cache_dir, [("train", "C_0000"), ("absent", "C_ab12")]
    )

    assert freed == CacheDirStats()
    assert cache_dir_stats(cache_dir) == CacheDirStats(
        total_bytes=80, entries=2
    )


def test_delete_entries_dry_run_reports_without_deleting(
    tmp_path: Path,
) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)
    entries = [("train", "C_ab12"), ("train", "E_9f00")]

    planned = delete_cache_entries(cache_dir, entries, dry_run=True)

    assert planned == CacheDirStats(total_bytes=100, entries=2)
    assert delete_cache_entries(cache_dir, entries) == planned


def test_delete_entries_leaves_everything_it_was_not_given(
    tmp_path: Path,
) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)

    delete_cache_entries(cache_dir, [("train", "E_9f00")])

    assert cache_dir_stats(cache_dir) == CacheDirStats(
        total_bytes=85, entries=1
    )
    assert (cache_dir / ".nb-export.json").exists()


def test_clean_cache_dir_skips_a_directory_that_holds_no_entries(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `save_path` can point the cache at a project. Its directories are
    not blocks, and deleting them would take the project with them."""
    project = tmp_path
    (project / ".git").mkdir()
    (project / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("print('hi')\n")
    (project / "empty").mkdir()
    block = populate_lazy_block(project)
    monkeypatch.setattr(_loggers.marimo_logger(), "propagate", True)

    with caplog.at_level(logging.WARNING):
        freed = clean_cache_dir(project)

    assert freed.entries == 2
    assert not block.exists()
    assert (project / ".git" / "HEAD").exists()
    assert (project / "src" / "app.py").exists()
    assert not (project / "empty").exists()
    assert "holds no cache entries" in caplog.text


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not restrict writes on Windows"
)
def test_delete_entries_keeps_the_blobs_of_a_marker_that_stays(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A marker that cannot be removed can still be read, so the blobs it
    names must stay, and the entry does not count as deleted."""
    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)
    block.chmod(0o555)
    if os.access(block / "C_ab12.jsonl", os.W_OK) and os.getuid() == 0:
        block.chmod(0o755)
        pytest.skip("chmod does not restrict writes for this user")
    monkeypatch.setattr(_loggers.marimo_logger(), "propagate", True)

    try:
        with caplog.at_level(logging.WARNING):
            freed = delete_cache_entries(cache_dir, [("train", "C_ab12")])
    finally:
        block.chmod(0o755)

    assert freed.entries == 0
    assert (block / "C_ab12.jsonl").exists()
    assert (block / "ab12" / "return.pickle").exists()
    assert "Could not remove C_ab12" in caplog.text


def test_block_dir_name_drops_the_stars_a_loader_drops() -> None:
    assert block_dir_name("*train*") == "train"
