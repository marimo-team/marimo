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


def write_manifest(
    cache_dir: Path, notebook: Path, nodes: dict[str, dict[str, set[str]]]
) -> Path:
    path = cache_dir / manifest_name(notebook)
    path.write_bytes(
        CacheManifest(notebook="../../nb.py", nodes=nodes).to_bytes()
    )
    return path


def test_apply_keeps_records_written_after_the_plan(tmp_path: Path) -> None:
    notebook = tmp_path / "nb.py"
    cache_dir = tmp_path / "__marimo__" / "cache"
    block = cache_dir / "train"
    block.mkdir(parents=True)
    (block / "C_ab12ab12ab12ab12ab12ab.pickle").write_bytes(b"x" * 10)
    manifest = write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {"C_ab12ab12ab12ab12ab12ab"}}}
    )
    plan = plan_clean(cache_dir, notebook)

    # A kernel records a new entry between planning and deletion.
    (block / "C_77e077e077e077e077e077.pickle").write_bytes(b"x" * 10)
    write_manifest(
        cache_dir,
        notebook,
        {
            "3f9c": {
                "train": {
                    "C_ab12ab12ab12ab12ab12ab",
                    "C_77e077e077e077e077e077",
                }
            }
        },
    )
    freed = apply_clean(plan)

    assert freed == CacheDirStats(total_bytes=10, entries=1)
    assert not (block / "C_ab12ab12ab12ab12ab12ab.pickle").exists()
    assert (block / "C_77e077e077e077e077e077.pickle").exists()
    assert CacheManifest.from_bytes(manifest.read_bytes()).nodes == {
        "3f9c": {"train": {"C_77e077e077e077e077e077"}}
    }


def test_apply_does_not_recreate_a_manifest_removed_meanwhile(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "nb.py"
    cache_dir = tmp_path / "__marimo__" / "cache"
    block = cache_dir / "train"
    block.mkdir(parents=True)
    (block / "C_ab12ab12ab12ab12ab12ab.pickle").write_bytes(b"x" * 10)
    manifest = write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {"C_ab12ab12ab12ab12ab12ab"}}}
    )
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
    notebook = tmp_path / "nb.py"
    cache_dir = tmp_path / "__marimo__" / "cache"
    block = cache_dir / "train"
    block.mkdir(parents=True)
    entry = block / "C_ab12ab12ab12ab12ab12ab.pickle"
    entry.write_bytes(b"x" * 10)
    manifest = write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {"C_ab12ab12ab12ab12ab12ab"}}}
    )
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
    assert CacheManifest.from_bytes(manifest.read_bytes()).nodes == {
        "3f9c": {"train": {"C_ab12ab12ab12ab12ab12ab"}}
    }


def test_apply_block_clean_leaves_entries_written_after_the_plan(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "__marimo__" / "cache"
    block = cache_dir / "train"
    block.mkdir(parents=True)
    (block / "C_ab12ab12ab12ab12ab12ab.pickle").write_bytes(b"x" * 10)
    plan = plan_block_clean(cache_dir)

    # A kernel writes while the prompt waits for an answer.
    (block / "C_77e077e077e077e077e077.pickle").write_bytes(b"x" * 10)
    freed = apply_block_clean(plan)

    assert plan.freed == freed == CacheDirStats(total_bytes=10, entries=1)
    assert not (block / "C_ab12ab12ab12ab12ab12ab.pickle").exists()
    assert (
        block / "C_77e077e077e077e077e077.pickle"
    ).read_bytes() == b"x" * 10
