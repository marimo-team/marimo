# Copyright 2026 Marimo. All rights reserved.
"""`bundle_cache_export` — bundling an executed export's caches.

When cell caching is enabled, the executed kernel flushes its caches on
shutdown and writes a per-notebook export manifest next to the blobs in
`__marimo__/cache/`; the export reads that manifest and copies exactly those
files into `<out_dir>/public/cache/`. These tests exercise the copy against a
synthetic `__marimo__/cache` tree; no kernel run required.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from marimo._save.stores.file import export_manifest_name
from marimo._server.export import bundle_cache_export
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import notebook_output_dir

if TYPE_CHECKING:
    from pathlib import Path


def _notebook(tmp_path: Path) -> MarimoPath:
    nb = tmp_path / "nb.py"
    nb.write_text("import marimo\napp = marimo.App()\n")
    return MarimoPath(str(nb))


def _cache_dir(tmp_path: Path) -> Path:
    cache = notebook_output_dir(tmp_path) / "cache"
    cache.mkdir(parents=True)
    return cache


def _write_manifest(
    cache: Path, notebook: MarimoPath, keys: list[str]
) -> None:
    name = export_manifest_name(notebook.absolute_name)
    (cache / name).write_text(json.dumps(keys))


def test_no_manifest_is_a_noop(tmp_path: Path) -> None:
    _cache_dir(tmp_path)  # cache dir exists, but no manifest was written
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    bundle_cache_export(_notebook(tmp_path), out_dir)
    assert not (out_dir / "public" / "cache").exists()


def test_keys_copied(tmp_path: Path) -> None:
    cache = _cache_dir(tmp_path)
    nb = _notebook(tmp_path)
    (cache / "lazy").mkdir()
    (cache / "lazy" / "E_abc.jsonl").write_bytes(b"manifest-line\n")
    (cache / "lazy" / "blob.npy").write_bytes(b"\x93NUMPY")
    _write_manifest(cache, nb, ["lazy/E_abc.jsonl", "lazy/blob.npy"])

    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    bundle_cache_export(nb, out_dir)

    dst = out_dir / "public" / "cache"
    assert (dst / "lazy" / "E_abc.jsonl").read_bytes() == b"manifest-line\n"
    assert (dst / "lazy" / "blob.npy").read_bytes() == b"\x93NUMPY"


def test_missing_listed_file_skipped(tmp_path: Path) -> None:
    cache = _cache_dir(tmp_path)
    nb = _notebook(tmp_path)
    (cache / "present.bin").write_bytes(b"ok")
    _write_manifest(cache, nb, ["present.bin", "evicted.bin"])

    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    bundle_cache_export(nb, out_dir)

    dst = out_dir / "public" / "cache"
    assert (dst / "present.bin").exists()
    assert not (dst / "evicted.bin").exists()


def test_keys_outside_session_not_bundled(tmp_path: Path) -> None:
    """Only manifest-listed keys ship — other cache files on disk stay."""
    cache = _cache_dir(tmp_path)
    nb = _notebook(tmp_path)
    (cache / "mine.bin").write_bytes(b"mine")
    (cache / "other.bin").write_bytes(b"other-session")
    _write_manifest(cache, nb, ["mine.bin"])

    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    bundle_cache_export(nb, out_dir)

    dst = out_dir / "public" / "cache"
    assert (dst / "mine.bin").exists()
    assert not (dst / "other.bin").exists()


def test_corrupt_manifest_is_a_noop(tmp_path: Path) -> None:
    cache = _cache_dir(tmp_path)
    nb = _notebook(tmp_path)
    (cache / "mine.bin").write_bytes(b"mine")
    name = export_manifest_name(nb.absolute_name)
    (cache / name).write_text("not json{")

    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    bundle_cache_export(nb, out_dir)

    assert not (out_dir / "public" / "cache").exists()


def test_path_traversal_key_rejected(tmp_path: Path) -> None:
    """A tampered/stale manifest key can't escape the cache dir."""
    cache = _cache_dir(tmp_path)
    nb = _notebook(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"top secret")
    (cache / "ok.bin").write_bytes(b"ok")
    _write_manifest(cache, nb, ["../secret.txt", "/etc/hosts", "ok.bin"])

    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    bundle_cache_export(nb, out_dir)

    dst = out_dir / "public" / "cache"
    assert (dst / "ok.bin").exists()
    assert not (dst / ".." / "secret.txt").exists()
    assert list(dst.rglob("*")) == [dst / "ok.bin"]
