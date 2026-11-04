# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._save.cache_dirs import CacheDirStats
from marimo._save.prune import PrunePlan, apply_prune, plan_prune
from tests._cli.test_cli_cache import (
    H2,
    RECORD,
    H,
    path_hash_of,
    read_manifest,
    tracked_notebook,
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
    blobs = write_orphan_blobs(cache_dir, "train", H)
    plan = plan_prune(cache_dir)
    assert plan.orphans == {"train": frozenset({H})}

    (cache_dir / "train" / f"C_{H}.jsonl").write_bytes(b"x" * 10)
    freed = apply_prune(plan)

    assert freed == CacheDirStats()
    assert (blobs / "return.pickle").exists()
