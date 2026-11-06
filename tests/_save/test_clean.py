# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import marimo._save.clean as clean_module
from marimo._save.cache_dirs import CacheDirStats
from marimo._save.clean import (
    apply_block_clean,
    apply_clean,
    plan_block_clean,
    plan_clean,
)
from marimo._save.manifest import CacheManifest, manifest_name

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

    import pytest

H = "ab12ab12ab12ab12ab12ab"
H2 = "77e077e077e077e077e077"


def write_manifest(
    cache_dir: Path, notebook: Path, nodes: dict[str, dict[str, set[str]]]
) -> Path:
    path = cache_dir / manifest_name(notebook)
    path.write_bytes(
        CacheManifest(notebook="../../nb.py", nodes=nodes).to_bytes()
    )
    return path


def read_manifest(path: Path) -> dict[str, dict[str, set[str]]]:
    return CacheManifest.from_bytes(path.read_bytes()).nodes


def tracked_entry(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """A 10 B inline entry in block `train`, recorded for a notebook.

    Returns the notebook, the cache directory, the entry, and the manifest.
    """
    notebook = tmp_path / "nb.py"
    cache_dir = tmp_path / "__marimo__" / "cache"
    block = cache_dir / "train"
    block.mkdir(parents=True)
    entry = block / f"C_{H}.pickle"
    entry.write_bytes(b"x" * 10)
    manifest = write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {f"C_{H}"}}}
    )
    return notebook, cache_dir, entry, manifest


def test_plan_clean_selects_the_named_blocks(tmp_path: Path) -> None:
    """A name is matched as the loader writes it, stars dropped."""
    notebook, cache_dir, _entry, _manifest = tracked_entry(tmp_path)
    write_manifest(
        cache_dir,
        notebook,
        {"3f9c": {"train": {f"C_{H}"}, "evaluate": {f"C_{H2}"}}},
    )

    plan = plan_clean(cache_dir, notebook, ["*train*"])

    assert plan.entries == {("train", f"C_{H}")}
    assert plan.freed == CacheDirStats(total_bytes=10, entries=1)


def test_apply_keeps_records_written_after_the_plan(tmp_path: Path) -> None:
    notebook, cache_dir, entry, manifest = tracked_entry(tmp_path)
    plan = plan_clean(cache_dir, notebook)

    # A kernel records a new entry between planning and deletion.
    (entry.parent / f"C_{H2}.pickle").write_bytes(b"x" * 10)
    write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {f"C_{H}", f"C_{H2}"}}}
    )
    freed = apply_clean(plan)

    assert freed == CacheDirStats(total_bytes=10, entries=1)
    assert not entry.exists()
    assert (entry.parent / f"C_{H2}.pickle").exists()
    assert read_manifest(manifest) == {"3f9c": {"train": {f"C_{H2}"}}}


def test_apply_does_not_recreate_a_manifest_removed_meanwhile(
    tmp_path: Path,
) -> None:
    notebook, cache_dir, _entry, manifest = tracked_entry(tmp_path)
    plan = plan_clean(cache_dir, notebook)

    manifest.unlink()
    freed = apply_clean(plan)

    assert freed == CacheDirStats(total_bytes=10, entries=1)
    assert not manifest.exists()


def test_apply_keeps_the_record_of_an_entry_recreated_meanwhile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A kernel can write the same entry again between the deletion and
    the manifest rewrite. The record then still names a file."""
    notebook, cache_dir, entry, manifest = tracked_entry(tmp_path)
    plan = plan_clean(cache_dir, notebook)
    delete = clean_module.delete_cache_entries

    def delete_then_recreate(
        cache_dir: Path, entries: Collection[tuple[str, str]]
    ) -> CacheDirStats:
        freed = delete(cache_dir, entries)
        entry.write_bytes(b"x" * 10)
        return freed

    monkeypatch.setattr(
        clean_module, "delete_cache_entries", delete_then_recreate
    )
    freed = apply_clean(plan)

    assert freed == CacheDirStats(total_bytes=10, entries=1)
    assert entry.read_bytes() == b"x" * 10
    assert read_manifest(manifest) == {"3f9c": {"train": {f"C_{H}"}}}


def test_apply_block_clean_leaves_entries_written_after_the_plan(
    tmp_path: Path,
) -> None:
    _notebook, cache_dir, entry, _manifest = tracked_entry(tmp_path)
    plan = plan_block_clean(cache_dir)

    # A kernel writes while the prompt waits for an answer.
    (entry.parent / f"C_{H2}.pickle").write_bytes(b"x" * 10)
    freed = apply_block_clean(plan)

    assert plan.freed == freed == CacheDirStats(total_bytes=10, entries=1)
    assert not entry.exists()
    assert (entry.parent / f"C_{H2}.pickle").read_bytes() == b"x" * 10
