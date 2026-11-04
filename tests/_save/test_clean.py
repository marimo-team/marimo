# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._save.cache_dirs import CacheDirStats
from marimo._save.clean import apply_clean, plan_clean
from marimo._save.manifest import CacheManifest, manifest_name

if TYPE_CHECKING:
    from pathlib import Path


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
    (block / "C_ab12.pickle").write_bytes(b"x" * 10)
    manifest = write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {"C_ab12"}}}
    )
    plan = plan_clean(cache_dir, notebook)

    # A kernel records a new entry between planning and deletion.
    (block / "C_77e0.pickle").write_bytes(b"x" * 10)
    write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {"C_ab12", "C_77e0"}}}
    )
    freed = apply_clean(plan)

    assert freed == CacheDirStats(total_bytes=10, entries=1)
    assert not (block / "C_ab12.pickle").exists()
    assert (block / "C_77e0.pickle").exists()
    assert CacheManifest.from_bytes(manifest.read_bytes()).nodes == {
        "3f9c": {"train": {"C_77e0"}}
    }


def test_apply_does_not_recreate_a_manifest_removed_meanwhile(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "nb.py"
    cache_dir = tmp_path / "__marimo__" / "cache"
    block = cache_dir / "train"
    block.mkdir(parents=True)
    (block / "C_ab12.pickle").write_bytes(b"x" * 10)
    manifest = write_manifest(
        cache_dir, notebook, {"3f9c": {"train": {"C_ab12"}}}
    )
    plan = plan_clean(cache_dir, notebook)

    manifest.unlink()
    freed = apply_clean(plan)

    assert freed == CacheDirStats(total_bytes=10, entries=1)
    assert not manifest.exists()
