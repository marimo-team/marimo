# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pytest

from marimo._save.cache_dirs import CacheDirStats
from marimo._save.prune import PrunePlan, apply_prune, plan_prune
from tests._cli.test_cli_cache import (
    H2,
    NOTEBOOK,
    RECORD,
    H,
    path_hash_of,
    read_manifest,
    tracked_notebook,
    write_entry,
    write_lazy_entry,
    write_manifest,
    write_orphan_blobs,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_plan_of_a_cache_directory_that_does_not_exist(tmp_path: Path) -> None:
    cache_dir = tmp_path / "__marimo__" / "cache"

    plan = plan_prune(cache_dir)

    assert plan == PrunePlan(cache_dir)
    assert not cache_dir.exists()


def test_apply_keeps_records_written_after_the_plan(tmp_path: Path) -> None:
    notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    live = path_hash_of(notebook, "x")
    plan = plan_prune(cache_dir)
    assert plan.entries == {("train", f"C_{H}")}

    # A kernel records a new entry between planning and deletion.
    (cache_dir / "train" / f"C_{H2}.pickle").write_bytes(b"x" * 10)
    write_manifest(
        cache_dir, notebook, {**RECORD, live: {"train": {f"C_{H2}"}}}
    )
    freed = apply_prune(plan)

    assert freed == CacheDirStats(total_bytes=30, entries=1)
    assert not (cache_dir / "train" / f"C_{H}.jsonl").exists()
    assert (cache_dir / "train" / f"C_{H2}.pickle").exists()
    assert read_manifest(manifest) == {live: {"train": {f"C_{H2}"}}}


def test_apply_does_not_recreate_a_manifest_removed_meanwhile(
    tmp_path: Path,
) -> None:
    _notebook, cache_dir, manifest = tracked_notebook(tmp_path)
    plan = plan_prune(cache_dir)

    manifest.unlink()
    freed = apply_prune(plan)

    assert freed == CacheDirStats(total_bytes=30, entries=1)
    assert not manifest.exists()


def test_apply_keeps_a_blob_directory_a_marker_came_to_read(
    tmp_path: Path,
) -> None:
    """The kernel that was writing the blobs finishes between the plan and
    the deletion. Its marker now reads them, so they are kept."""
    cache_dir = tmp_path / "__marimo__" / "cache"
    cache_dir.mkdir(parents=True)
    write_lazy_entry(cache_dir, "train", H2)
    blobs = write_orphan_blobs(cache_dir, "train", H)
    plan = plan_prune(cache_dir)
    assert plan.orphans == {"train": frozenset({H})}
    assert plan.claimed == 0

    (cache_dir / "train" / f"C_{H}.jsonl").write_bytes(b"x" * 10)
    freed = apply_prune(plan)

    assert freed == CacheDirStats()
    assert (blobs / "return.pickle").exists()


def test_plan_lists_a_block_once_however_many_entries_it_shares(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An entry that is dead for one notebook and live for another is kept,
    and deciding that must not list the block once per entry."""
    from marimo._save import cache_dirs

    def shared_cache(root: Path, count: int) -> Path:
        root.mkdir()
        notebook = root / "nb.py"
        notebook.write_text(NOTEBOOK)
        other = root / "other.py"
        other.write_text(NOTEBOOK)
        cache_dir = root / "__marimo__" / "cache"
        keys = {f"C_{H[:-2]}{i:02d}" for i in range(count)}
        for key in keys:
            write_entry(cache_dir, "train", f"{key}.pickle", 10)
        write_manifest(cache_dir, notebook, {"dead": {"train": keys}})
        write_manifest(
            cache_dir, other, {path_hash_of(other, "x"): {"train": keys}}
        )
        return cache_dir

    listings: list[Path] = []
    index_block = cache_dirs._index_block

    def count(block: Path) -> object:
        listings.append(block)
        return index_block(block)

    monkeypatch.setattr(cache_dirs, "_index_block", count)
    few = shared_cache(tmp_path / "few", 1)
    plan_prune(few)
    with_one = listings.count(few / "train")
    listings.clear()
    many = shared_cache(tmp_path / "many", 12)
    plan = plan_prune(many)

    assert plan.deletes_nothing()
    assert listings.count(many / "train") == with_one


def test_apply_takes_orphans_beside_the_last_entry(tmp_path: Path) -> None:
    """A dry run plans both, so the real run must delete both, even though
    the entry that qualified the block is itself planned."""
    _notebook, cache_dir, _manifest = tracked_notebook(tmp_path)
    write_orphan_blobs(cache_dir, "train", H2)
    plan = plan_prune(cache_dir)

    freed = apply_prune(plan)

    assert plan.freed == freed == CacheDirStats(total_bytes=50, entries=2)
    assert not (cache_dir / "train").exists()


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not restrict reads on Windows"
)
def test_apply_reports_a_cache_root_that_cannot_be_listed(
    tmp_path: Path,
) -> None:
    """The failure is counted when the plan is applied too, so a run that
    prunes another cache still exits with an error for this one."""
    _notebook, cache_dir, _manifest = tracked_notebook(tmp_path)
    cache_dir.chmod(0o000)
    if os.access(cache_dir, os.R_OK):
        cache_dir.chmod(0o755)
        pytest.skip("chmod does not restrict reads for this user")

    try:
        plan = plan_prune(cache_dir)
        freed = apply_prune(plan)
    finally:
        cache_dir.chmod(0o755)

    assert plan.freed == freed == CacheDirStats(failures=1)
    assert (cache_dir / "train" / f"C_{H}.jsonl").exists()
