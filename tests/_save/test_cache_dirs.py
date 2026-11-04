# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

import pytest

from marimo import _loggers
from marimo._save.cache_dirs import (
    CacheDirError,
    CacheDirStats,
    NotANotebookError,
    block_dir_name,
    cache_dir_stats,
    clean_cache_dir,
    delete_blocks,
    delete_cache_entries,
    directory_cache_dir,
    entry_bytes,
    missing_entries,
    notebook_cache_dir,
    partial_write_name,
    resolve_cache_dirs,
    select_blocks,
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
    (block / "C_ab12ab12ab12ab12ab12ab.jsonl").write_bytes(b"x" * 10)
    (block / "E_9f009f009f009f009f009f.pickle").write_bytes(b"y" * 20)
    # A lazily loaded value is split over a directory of blobs, named after
    # the hash its entry file also names.
    blob = block / "ab12ab12ab12ab12ab12ab"
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
    leftover = (
        cache_dir
        / "train"
        / partial_write_name("C_77e077e077e077e077e077.pickle")
    )
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
    (cache_dir / "train" / "C_ab12ab12ab12ab12ab12ab.jsonl").unlink()

    assert cache_dir_stats(cache_dir) == CacheDirStats(
        total_bytes=95, entries=2
    )


def test_cache_dir_stats_counts_several_blocks(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)
    other = cache_dir / "evaluate"
    other.mkdir()
    (other / "C_77e077e077e077e077e077.pickle").write_bytes(b"x" * 7)

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
    (unreadable / "C_77e077e077e077e077e077.pickle").write_bytes(b"x" * 7)
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
    link = block / "C_ab12ab12ab12ab12ab12ab.jsonl"
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
    (outside / "C_ab12ab12ab12ab12ab12ab.jsonl").write_bytes(b"x" * 4096)
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


def test_entry_bytes(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)

    assert entry_bytes(cache_dir / "train") == 100
    assert entry_bytes(cache_dir / "train" / "ab12ab12ab12ab12ab12ab") == 70
    assert (
        entry_bytes(cache_dir / "train" / "C_ab12ab12ab12ab12ab12ab.jsonl")
        == 10
    )
    assert entry_bytes(cache_dir / "never-written") == 0


H = "ab12ab12ab12ab12ab12ab"
H2 = "77e077e077e077e077e077"
H3 = "9f009f009f009f009f009f"
GONE = "gonegonegonegonegonego"


def populate_lazy_block(cache_dir: Path, block_name: str = "train") -> Path:
    """Write a block with two lazy entries, 30 B and 50 B with their blobs."""
    block = cache_dir / block_name
    for entry_hash, size in ((H, 20), (H2, 40)):
        blobs = block / entry_hash
        blobs.mkdir(parents=True)
        (blobs / "return.pickle").write_bytes(b"y" * size)
        (block / f"C_{entry_hash}.jsonl").write_bytes(b"x" * 10)
    return block


def test_block_dir_name_spells_a_name_as_a_loader_does() -> None:
    assert block_dir_name("train") == "train"
    assert block_dir_name("train/v2") == "train_v2"
    assert block_dir_name("épochs") == "_pochs"
    assert block_dir_name("*train*") == "train"


def test_clean_removes_every_block_and_its_blobs(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)
    populate_lazy_block(cache_dir, "evaluate")

    freed = clean_cache_dir(cache_dir)

    assert freed == CacheDirStats(total_bytes=180, entries=4)
    # The manifests describing the cache outlive the entries they describe.
    assert [path.name for path in cache_dir.iterdir()] == [".nb-export.json"]


@pytest.mark.parametrize(
    ("names", "removed"),
    [
        (["evaluate"], "evaluate"),
        (["train/v2"], "train_v2"),
        (["*train*"], "train"),
        (["absent"], None),
    ],
)
def test_clean_selects_blocks_by_name(
    tmp_path: Path, names: list[str], removed: str | None
) -> None:
    """A name is matched as the loader writes it to disk."""
    cache_dir = make_cache_dir(tmp_path)
    for block in ("train", "train_v2", "evaluate"):
        populate_lazy_block(cache_dir, block)

    freed = clean_cache_dir(cache_dir, names)

    if removed is None:
        assert freed == CacheDirStats()
    else:
        assert freed == CacheDirStats(total_bytes=80, entries=2)
        assert not (cache_dir / removed).exists()
    assert cache_dir_stats(cache_dir) == CacheDirStats(
        total_bytes=240 - freed.total_bytes, entries=6 - freed.entries
    )


def test_dry_run_reports_what_the_real_run_frees(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    populate_cache_dir(cache_dir)
    other = make_cache_dir(tmp_path, "other")
    populate_cache_dir(other)
    entries = [("train", f"C_{H}"), ("train", f"E_{H3}")]

    planned = clean_cache_dir(cache_dir, dry_run=True)
    planned_entries = delete_cache_entries(other, entries, dry_run=True)

    assert (
        planned == planned_entries == CacheDirStats(total_bytes=100, entries=2)
    )
    assert clean_cache_dir(cache_dir) == planned
    assert delete_cache_entries(other, entries) == planned_entries


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
    """Bytes a block did not give up are not reported as freed, and the
    marker of an entry whose blobs stayed is kept for another try."""
    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)
    kept = block / H
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

    assert freed == CacheDirStats(total_bytes=50, entries=1, failures=1)
    assert (kept / "return.pickle").read_bytes() == b"y" * 20
    assert (block / f"C_{H}.jsonl").exists()
    assert not (block / f"C_{H2}.jsonl").exists()
    assert str(block) in caplog.text


def test_delete_entries_takes_only_the_entries_named(tmp_path: Path) -> None:
    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)

    freed = delete_cache_entries(
        cache_dir,
        [("train", f"C_{H}"), ("train", f"C_{GONE}"), ("absent", f"C_{H}")],
    )

    assert freed == CacheDirStats(total_bytes=30, entries=1)
    assert sorted(path.name for path in block.iterdir()) == [
        H2,
        f"C_{H2}.jsonl",
    ]


def test_delete_entries_frees_shared_blobs_once(tmp_path: Path) -> None:
    """Two entries can read from the same directory of blobs. The blobs go
    with the last of those entries and are counted once."""
    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)
    (block / f"E_{H}.jsonl").write_bytes(b"x" * 10)
    both = [("train", f"C_{H}"), ("train", f"E_{H}")]

    planned = delete_cache_entries(cache_dir, both, dry_run=True)
    first = delete_cache_entries(cache_dir, both[:1])

    assert planned == CacheDirStats(total_bytes=40, entries=2)
    assert first == CacheDirStats(total_bytes=10, entries=1)
    assert (block / H / "return.pickle").read_bytes() == b"y" * 20
    assert (block / f"E_{H}.jsonl").exists()

    second = delete_cache_entries(cache_dir, both[1:])

    assert first + second == planned
    assert not (block / H).exists()


def test_delete_entries_refuses_a_name_no_cache_write_spells(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A manifest is a file like any other. What it names must be an entry."""
    outside = tmp_path / "model.bin"
    outside.write_bytes(b"o" * 40)
    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)
    (block / f"Z_{H}.pickle").write_bytes(b"z" * 5)
    (block / "utils").mkdir()
    (block / "utils" / "__init__.py").write_text("")
    monkeypatch.setattr(_loggers.marimo_logger(), "propagate", True)

    with caplog.at_level(logging.WARNING):
        freed = delete_cache_entries(
            cache_dir,
            [
                ("../..", "model"),
                ("train", ".."),
                ("train", "../../model"),
                # A separator is outside the key's character set, so no key
                # can name a parent, however its hash reads.
                ("train", "C_.."),
                # Without a type prefix a key names a directory of blobs.
                ("train", H),
                # Not a cache type.
                ("train", f"Z_{H}"),
                # Five characters is not a length stripped base64 can have.
                ("train", "C_utils"),
            ],
        )

    assert freed == CacheDirStats()
    assert outside.read_bytes() == b"o" * 40
    assert (block / f"Z_{H}.pickle").exists()
    assert (block / "utils" / "__init__.py").exists()
    assert (block / f"C_{H}.jsonl").exists()
    assert "no cache entry can be named that" in caplog.text


def test_delete_entries_removes_blobs_before_the_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A marker that outlives a failed blob removal keeps the entry on
    record, so the blobs go first."""
    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)
    (block / f"E_{H}.jsonl").write_bytes(b"shared")
    markers_present: list[bool] = []
    remove_tree = shutil.rmtree

    def spy(directory: Path, *, ignore_errors: bool = False) -> None:
        markers_present.append(
            (block / f"C_{H}.jsonl").exists()
            and (block / f"E_{H}.jsonl").exists()
        )
        remove_tree(directory, ignore_errors=ignore_errors)

    monkeypatch.setattr(shutil, "rmtree", spy)
    freed = delete_cache_entries(
        cache_dir, [("train", f"C_{H}"), ("train", f"E_{H}")]
    )

    assert markers_present == [True]
    assert freed == CacheDirStats(total_bytes=36, entries=2)
    assert not (block / H).exists()
    assert not (block / f"C_{H}.jsonl").exists()
    assert not (block / f"E_{H}.jsonl").exists()


def test_delete_entries_leaves_a_write_that_is_not_finished(
    tmp_path: Path,
) -> None:
    """A writer publishes by renaming a sibling into place. Deleting the
    sibling breaks that rename, so it is never matched as an entry."""
    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)
    sibling = block / partial_write_name(f"C_{H}.jsonl")
    sibling.write_bytes(b"p" * 8)

    freed = delete_cache_entries(cache_dir, [("train", f"C_{H}")])

    assert freed == CacheDirStats(total_bytes=30, entries=1)
    assert sibling.read_bytes() == b"p" * 8


def test_clean_keeps_what_is_not_a_cache_entry(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `save_path` can point the cache at a project, and only entries and
    their blobs go. A file is an entry only if it has a cache-type prefix
    and a digest at least as long as the shortest digest that a writer
    produces, so project files that look like keys stay, and so do
    directories with names that look like their hashes. A directory that
    holds no entry is not a block."""
    project = tmp_path
    (project / ".git").mkdir()
    (project / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (project / "empty").mkdir()
    orphan = project / "stale" / H / "return.pickle"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"y" * 20)
    src = project / "src"
    src.mkdir()
    for name, text in (
        ("app.py", "print('hi')\n"),
        ("C_utils.py", "def f(): ...\n"),
        ("utils/__init__.py", ""),
        ("P_data.json", "{}"),
        ("data/rows.csv", "1,2\n"),
        ("records.json", "{}"),
        ("records/a.json", "{}"),
    ):
        (src / name).parent.mkdir(exist_ok=True)
        (src / name).write_text(text)
    (src / f"C_{H2}.pickle").write_bytes(b"x" * 10)
    block = populate_lazy_block(project)
    monkeypatch.setattr(_loggers.marimo_logger(), "propagate", True)

    with caplog.at_level(logging.WARNING):
        planned = clean_cache_dir(project, dry_run=True)
        freed = clean_cache_dir(project)

    assert planned == freed == CacheDirStats(total_bytes=90, entries=3)
    assert not block.exists()
    assert not (src / f"C_{H2}.pickle").exists()
    assert {path.name for path in src.rglob("*") if path.is_file()} == {
        "C_utils.py",
        "__init__.py",
        "a.json",
        "app.py",
        "P_data.json",
        "records.json",
        "rows.csv",
    }
    assert (project / ".git" / "HEAD").exists()
    assert (project / "empty").is_dir()
    assert orphan.read_bytes() == b"y" * 20
    assert "holds no cache entries" in caplog.text
    assert f"Kept {src}" in caplog.text


def test_clean_takes_entries_written_at_the_root(tmp_path: Path) -> None:
    """A cache named by stars alone writes its entries at the root."""
    cache_dir = make_cache_dir(tmp_path)
    (cache_dir / f"C_{H}.jsonl").write_bytes(b"x" * 10)
    (cache_dir / ".nb-export.json").write_bytes(b"m" * 3)
    populate_lazy_block(cache_dir)

    assert clean_cache_dir(cache_dir, ["***"]) == CacheDirStats(
        total_bytes=10, entries=1
    )
    assert not (cache_dir / f"C_{H}.jsonl").exists()
    assert (cache_dir / ".nb-export.json").exists()
    assert (cache_dir / "train" / f"C_{H}.jsonl").exists()

    (cache_dir / f"C_{H2}.pickle").write_bytes(b"x" * 10)

    assert delete_cache_entries(cache_dir, [("", f"C_{H2}")]) == CacheDirStats(
        total_bytes=10, entries=1
    )
    assert cache_dir.is_dir()


def test_delete_entries_keeps_blobs_a_new_marker_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A writer can write a marker for the same blobs between the listing
    and the removal of the blobs."""
    from marimo._save import cache_dirs

    cache_dir = make_cache_dir(tmp_path)
    block = populate_lazy_block(cache_dir)
    index_block = cache_dirs._index_block

    def index_then_publish(*args: object, **kwargs: object) -> object:
        index = index_block(*args, **kwargs)
        (block / f"E_{H}.jsonl").write_bytes(b"new")
        return index

    monkeypatch.setattr(cache_dirs, "_index_block", index_then_publish)
    freed = delete_cache_entries(cache_dir, [("train", f"C_{H}")])

    assert freed == CacheDirStats(total_bytes=10, entries=1)
    assert not (block / f"C_{H}.jsonl").exists()
    assert (block / H / "return.pickle").read_bytes() == b"y" * 20


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not restrict reads on Windows"
)
def test_a_block_that_cannot_be_listed_is_a_failure(tmp_path: Path) -> None:
    """A manifest clean stops at it. A directory clean reports it and
    cleans the other blocks."""
    cache_dir = make_cache_dir(tmp_path)
    populate_lazy_block(cache_dir, "train")
    sealed = populate_lazy_block(cache_dir, "evaluate")
    sealed.chmod(0o000)
    if os.access(sealed, os.R_OK):
        sealed.chmod(0o755)
        pytest.skip("chmod does not restrict reads for this user")

    try:
        with pytest.raises(OSError):
            delete_cache_entries(cache_dir, [("evaluate", f"C_{H}")])
        selection = select_blocks(cache_dir)
        planned = delete_blocks(cache_dir, selection, dry_run=True)
        freed = delete_blocks(cache_dir, selection)
    finally:
        sealed.chmod(0o755)

    assert selection[sealed] is None
    assert (
        planned
        == freed
        == CacheDirStats(total_bytes=80, entries=2, failures=1)
    )
    assert not (cache_dir / "train").exists()
    assert (sealed / f"C_{H}.jsonl").exists()


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlinks need a privileged user"
)
def test_resolve_refuses_linked_cache_dirs_when_deleting(
    tmp_path: Path,
) -> None:
    """The recursive search skips a link, and a deletion that resolves to
    one is refused. A link that PATH names directly is allowed."""
    other = make_cache_dir(tmp_path, "other")
    linked_cache = tmp_path / "a"
    (linked_cache / "__marimo__").mkdir(parents=True)
    link = linked_cache / "__marimo__" / "cache"
    link.symlink_to(other, target_is_directory=True)
    notebook = linked_cache / "nb.py"
    notebook.write_text(NOTEBOOK)
    linked_marimo = tmp_path / "b"
    linked_marimo.mkdir()
    (linked_marimo / "__marimo__").symlink_to(
        other.parent, target_is_directory=True
    )

    assert resolve_cache_dirs(tmp_path, recursive=True) == [other]
    assert resolve_cache_dirs(linked_cache) == [link]
    for path in (linked_cache, notebook, linked_marimo):
        with pytest.raises(CacheDirError, match="symbolic link"):
            resolve_cache_dirs(path, deleting=True)
    assert resolve_cache_dirs(link, deleting=True) == [link]


def test_delete_entries_keeps_a_directory_beside_an_inline_entry(
    tmp_path: Path,
) -> None:
    """Only a lazy marker names a directory of blobs."""
    cache_dir = make_cache_dir(tmp_path)
    block = cache_dir / "train"
    block.mkdir()
    (block / f"P_{H}.pickle").write_bytes(b"x" * 10)
    (block / H).mkdir()
    (block / H / "rows.csv").write_text("1,2\n")

    freed = delete_cache_entries(cache_dir, [("train", f"P_{H}")])

    assert freed == CacheDirStats(total_bytes=10, entries=1)
    assert not (block / f"P_{H}.pickle").exists()
    assert (block / H / "rows.csv").exists()


def test_missing_entries_lists_each_block_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record is missing when no file matches it. A directory of blobs
    without its marker matches no record, so it is left for prune."""
    from marimo._save import cache_dirs

    cache_dir = make_cache_dir(tmp_path)
    populate_lazy_block(cache_dir, "train")
    stale = populate_lazy_block(cache_dir, "evaluate")
    (stale / f"C_{H}.jsonl").unlink()
    listings: list[Path] = []
    index_block = cache_dirs._index_block

    def count(block: Path, *args: object, **kwargs: object) -> object:
        listings.append(block)
        return index_block(block, *args, **kwargs)

    monkeypatch.setattr(cache_dirs, "_index_block", count)
    missing = missing_entries(
        cache_dir,
        [
            ("train", f"C_{H}"),
            ("train", f"C_{H2}"),
            ("train", f"C_{GONE}"),
            ("evaluate", f"C_{H}"),
            ("evaluate", f"C_{H2}"),
            ("absent", f"C_{H}"),
            ("../..", f"C_{H}"),
        ],
    )

    assert sorted(listings) == [cache_dir / "evaluate", cache_dir / "train"]
    assert missing == {
        ("train", f"C_{GONE}"),
        ("evaluate", f"C_{H}"),
        ("absent", f"C_{H}"),
        ("../..", f"C_{H}"),
    }
    assert (stale / H / "return.pickle").exists()


def test_clean_takes_an_entry_with_any_suffix(tmp_path: Path) -> None:
    """A loader that uses a custom suffix is cleaned like any other, by the
    directory clean and from its records alike."""
    cache_dir = make_cache_dir(tmp_path)
    block = cache_dir / "train"
    block.mkdir()
    entry = block / f"C_{H}.custom"
    entry.write_bytes(b"x" * 10)

    assert clean_cache_dir(cache_dir) == CacheDirStats(
        total_bytes=10, entries=1
    )
    assert not entry.exists()

    block.mkdir()
    entry.write_bytes(b"x" * 10)

    assert delete_cache_entries(cache_dir, [("train", f"C_{H}")]) == (
        CacheDirStats(total_bytes=10, entries=1)
    )
    assert not entry.exists()


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlinks need a privileged user"
)
def test_delete_entries_refuses_a_linked_block(tmp_path: Path) -> None:
    """Files behind a link are neither deleted nor declared absent."""
    cache_dir = make_cache_dir(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    populate_lazy_block(elsewhere)
    (cache_dir / "train").symlink_to(
        elsewhere / "train", target_is_directory=True
    )

    with pytest.raises(CacheDirError, match="symbolic link"):
        delete_cache_entries(cache_dir, [("train", f"C_{H}")])
    with pytest.raises(CacheDirError, match="symbolic link"):
        missing_entries(cache_dir, [("train", f"C_{H}")])

    assert (elsewhere / "train" / f"C_{H}.jsonl").exists()
