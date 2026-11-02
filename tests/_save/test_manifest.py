# Copyright 2026 Marimo. All rights reserved.
"""The manifest format, and the runtime paths that write into it."""

from __future__ import annotations

import contextlib
import copy
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from marimo._config.config import DEFAULT_CONFIG
from marimo._runtime.context import get_context
from marimo._save.loaders.lazy import LazyStore, WasmLazyStore
from marimo._save.manifest import (
    MANIFEST_VERSION,
    CacheManifest,
    CorruptManifestError,
    UnsupportedManifestVersionError,
    flush_cache_manifest,
    flush_dirty_manifests,
    is_manifest_name,
    load_manifest,
    manifest_name,
)
from marimo._save.stores.dict_store import DictStore
from marimo._save.stores.file import FileStore
from marimo._save.stores.rest import RestStore
from marimo._save.stores.tiered import TieredStore
from tests._runtime._helpers.factories import default_app_metadata
from tests._runtime._helpers.session import mocked_kernel_session

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._runtime.runtime import Kernel
    from marimo._save.stores import Store
    from tests.conftest import ExecReqProvider

NOTEBOOK_SOURCE = "import marimo\n\napp = marimo.App()\n"


class TestManifestFormat:
    @staticmethod
    def test_round_trip() -> None:
        manifest = CacheManifest(
            notebook="../../nb.py",
            nodes={"3f9c": {"train": {"C_ab12", "C_77e0"}}},
            written_at="2026-09-01T00:00:00+00:00",
        )
        assert CacheManifest.from_bytes(manifest.to_bytes()) == manifest

    @staticmethod
    def test_merge_unions_keys() -> None:
        manifest = CacheManifest(nodes={"3f9c": {"train": {"C_ab12"}}})
        manifest.merge(
            CacheManifest(
                nodes={
                    "3f9c": {"train": {"C_77e0"}, "eval": {"E_0001"}},
                    "8d21": {"train": {"C_e4f9"}},
                }
            )
        )
        assert manifest.nodes == {
            "3f9c": {"train": {"C_ab12", "C_77e0"}, "eval": {"E_0001"}},
            "8d21": {"train": {"C_e4f9"}},
        }

    @staticmethod
    def test_merge_does_not_alias_the_other_manifest() -> None:
        records = {"3f9c": {"train": {"C_ab12"}}}
        manifest = CacheManifest()
        manifest.merge(CacheManifest(nodes=records))
        records["3f9c"]["train"].add("C_77e0")
        assert manifest.nodes == {"3f9c": {"train": {"C_ab12"}}}

    @staticmethod
    def test_evict_dead_returns_entries_and_keeps_live() -> None:
        manifest = CacheManifest(
            nodes={
                "dead": {"train": {"C_ab12", "C_77e0"}},
                "live": {"train": {"C_e4f9"}},
            }
        )
        assert manifest.evict_dead({"live"}) == {
            ("train", "C_ab12"),
            ("train", "C_77e0"),
        }
        assert manifest.nodes == {"live": {"train": {"C_e4f9"}}}
        assert manifest.entries() == {("train", "C_e4f9")}

    @staticmethod
    def test_corrupt_manifest_raises() -> None:
        with pytest.raises(CorruptManifestError):
            CacheManifest.from_bytes(b"{not json")
        with pytest.raises(CorruptManifestError):
            CacheManifest.from_bytes(b"[]")
        # A manifest with no version cannot be read under any rules.
        with pytest.raises(CorruptManifestError):
            CacheManifest.from_bytes(b'{"nodes": {}}')
        with pytest.raises(CorruptManifestError):
            CacheManifest.from_bytes(
                json.dumps(
                    {"version": 1, "nodes": {"3f9c": {"train": "C_ab12"}}}
                ).encode()
            )

    @staticmethod
    def test_newer_version_raises() -> None:
        payload = json.dumps(
            {"version": MANIFEST_VERSION + 1, "nodes": {}}
        ).encode()
        with pytest.raises(UnsupportedManifestVersionError):
            CacheManifest.from_bytes(payload)

    @staticmethod
    def test_same_stem_notebooks_get_distinct_names(tmp_path: Path) -> None:
        first = manifest_name(tmp_path / "a" / "nb.py")
        second = manifest_name(tmp_path / "b" / "nb.py")
        assert first != second
        assert first.startswith("nb-")
        assert first.endswith(".json")
        # Relative and absolute spellings of one notebook agree.
        assert manifest_name(Path("nb.py")) == manifest_name(
            Path.cwd() / "nb.py"
        )

    @staticmethod
    def test_a_long_stem_is_cut_to_fit_a_filename() -> None:
        """The digest tells manifests apart. The stem is only a label."""
        from marimo._save.manifest import MAX_SLUG_LENGTH

        name = manifest_name(Path("a" * 240 + ".py"))
        assert is_manifest_name(name)
        assert len(name) <= MAX_SLUG_LENGTH + len("-") + 16 + len(".json")
        assert name != manifest_name(Path("a" * 241 + ".py"))

    @staticmethod
    def test_a_notebook_path_that_is_not_utf8_gets_a_name() -> None:
        """A filesystem hands over a name it cannot decode as surrogates."""
        name = manifest_name(Path("/tmp/caf\udce9.py"))
        assert is_manifest_name(name)
        assert name != manifest_name(Path("/tmp/caf.py"))

    @staticmethod
    def test_only_a_cache_manifest_is_read_as_one() -> None:
        from marimo._save.stores.file import export_manifest_name

        assert is_manifest_name(manifest_name(Path("nb.py")))
        # Other bookkeeping a cache directory holds, and an entry.
        assert not is_manifest_name(export_manifest_name("nb.py"))
        assert not is_manifest_name("nb-0123456789abcdef.json.tmp0a1b2c3d")
        assert not is_manifest_name("C_ab12.pickle")

    @staticmethod
    def test_load_manifest_reads_what_put_stored(tmp_path: Path) -> None:
        store = FileStore(save_path=str(tmp_path))
        assert load_manifest(store, "absent.json") is None
        manifest = CacheManifest(nodes={"3f9c": {"train": {"C_ab12"}}})
        store.put("m.json", manifest.to_bytes())
        loaded = load_manifest(store, "m.json")
        assert loaded is not None
        assert loaded.nodes == manifest.nodes


class TestAtomicPut:
    @staticmethod
    def test_a_write_that_dies_midway_leaves_the_previous_value(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The new value is written elsewhere and renamed in, so a write that
        fails after its bytes are on disk still leaves a readable entry."""
        store = FileStore(save_path=str(tmp_path))
        store.put("entry", b"first")

        def explode(*_: object) -> None:
            raise OSError("no space left on device")

        monkeypatch.setattr(os, "replace", explode)
        with pytest.raises(OSError):
            store.put("entry", b"second-and-much-longer")

        assert store.get("entry") == b"first"
        # The half-written value never appears under a name a reader looks up,
        # and nothing is left behind.
        assert [path.name for path in tmp_path.iterdir()] == ["entry"]

    @staticmethod
    def test_clearing_reclaims_what_a_killed_write_left(
        tmp_path: Path,
    ) -> None:
        """Nothing runs after SIGKILL, so the leftover outlives the process
        that wrote it; clearing the block is what reclaims its bytes."""
        from marimo._save.cache_dirs import partial_write_name
        from marimo._save.loaders import PickleLoader

        store = FileStore(save_path=str(tmp_path))
        block = tmp_path / "train"
        block.mkdir()
        (block / "C_ab12.pickle").write_bytes(b"value")
        leftover = block / partial_write_name("C_77e0.pickle")
        leftover.write_bytes(b"half")

        PickleLoader("train", store=store).clear()
        assert list(block.iterdir()) == []


@contextlib.contextmanager
def _notebook_kernel(
    tmp_path: Path, *, cache_cells: bool = False, store: Store | None = None
) -> Iterator[tuple[Kernel, Path, Path]]:
    """A kernel for a notebook on disk, caching beside it."""
    notebook = tmp_path / "nb.py"
    notebook.write_text(NOTEBOOK_SOURCE, encoding="utf-8")
    cache_dir = tmp_path / "__marimo__" / "cache"
    user_config = None
    if cache_cells:
        user_config = copy.deepcopy(DEFAULT_CONFIG)
        user_config["runtime"]["cache_cells"] = True
    with mocked_kernel_session(
        app_metadata=default_app_metadata(filename=str(notebook)),
        user_config=user_config,
    ) as tk:
        # Pin the store. The ambient config can point a developer's cache
        # somewhere else entirely.
        tk.ctx.cache.store = store or FileStore(save_path=str(cache_dir))
        yield tk.kernel, notebook, cache_dir


def _manifest(notebook: Path, cache_dir: Path) -> dict[str, Any]:
    return json.loads(
        (cache_dir / manifest_name(notebook)).read_text(encoding="utf-8")
    )


def _entry_keys(manifest: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (block, key)
        for blocks in manifest["nodes"].values()
        for block, keys in blocks.items()
        for key in keys
    }


@contextlib.contextmanager
def _recorded_puts(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Collect the keys written through `FileStore` while running."""
    original_put = FileStore.put
    keys: list[str] = []

    def record(self: FileStore, key: str, value: bytes) -> bool:
        keys.append(key)
        return original_put(self, key, value)

    monkeypatch.setattr(FileStore, "put", record)
    yield keys


class TestRecording:
    @staticmethod
    async def test_failed_cache_flush_does_not_record_entry(
        tmp_path: Path,
        exec_req: ExecReqProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from marimo._save.loaders import PickleLoader

        def fail_flush(_self: PickleLoader) -> None:
            raise OSError("Cache write failed")

        monkeypatch.setattr(PickleLoader, "save_cache", lambda *_: True)
        monkeypatch.setattr(PickleLoader, "flush", fail_flush)
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        "with mo.persistent_cache('train', method='pickle'):\n    x = 42\n"
                    ),
                ]
            )
            assert k.globals["x"] == 42
            assert k.stderr.messages
            assert not (cache_dir / manifest_name(notebook)).exists()

    @staticmethod
    async def test_with_block_records_its_entry(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        "with mo.persistent_cache('train'):\n    x = 42\n"
                    ),
                ]
            )
            assert not k.stderr.messages
            assert k.globals["x"] == 42

            manifest = _manifest(notebook, cache_dir)
            assert manifest["version"] == MANIFEST_VERSION
            assert Path(manifest["notebook"]) == Path("../../nb.py")
            entries = _entry_keys(manifest)
            assert len(entries) == 1
            block, key = entries.pop()
            assert block == "train"
            assert (cache_dir / block / f"{key}.jsonl").exists()

    @staticmethod
    async def test_records_accumulate_across_edits(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        """A rerun under changed code adds a key. It never replaces one."""
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            setup = exec_req.get("import marimo as mo")
            block = exec_req.get(
                "epochs = 2\nwith mo.persistent_cache('train'):\n"
                "    model = epochs * 2\n"
            )
            await k.run([setup, block])
            await k.run(
                [
                    exec_req.get_with_id(
                        block.cell_id,
                        "epochs = 5\nwith mo.persistent_cache('train'):\n"
                        "    model = epochs * 2\n",
                    )
                ]
            )
            assert not k.stderr.messages

            manifest = _manifest(notebook, cache_dir)
            entries = _entry_keys(manifest)
            assert len(entries) == 2
            assert {block_name for block_name, _ in entries} == {"train"}

    @staticmethod
    async def test_records_under_the_defining_cell(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        """A function cached in one cell and called from another records
        against the cell that defines it, the one prune recompiles."""
        from marimo._save.hash import hash_cell_closure

        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            setup = exec_req.get("import marimo as mo")
            define = exec_req.get(
                "@mo.persistent_cache\ndef square(n):\n    return n * n\n"
            )
            call = exec_req.get("answer = square(7)")
            await k.run([setup, define, call])
            assert not k.stderr.messages
            assert k.globals["answer"] == 49

            manifest = _manifest(notebook, cache_dir)
            assert set(manifest["nodes"]) == {
                hash_cell_closure(define.cell_id, k.graph).hex()
            }
            assert (
                hash_cell_closure(call.cell_id, k.graph).hex()
                not in (manifest["nodes"])
            )

    @staticmethod
    async def test_records_merge_with_an_earlier_session(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        """A session records what it produced without forgetting what an
        earlier one, running other cells, left in the same directory."""
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        "with mo.persistent_cache('train'):\n    x = 42\n"
                    ),
                ]
            )
            written = _entry_keys(_manifest(notebook, cache_dir))

        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        "with mo.persistent_cache('eval'):\n    y = 7\n"
                    ),
                ]
            )
            assert not k.stderr.messages
            entries = _entry_keys(_manifest(notebook, cache_dir))

        assert written < entries
        assert {block for block, _ in entries} == {"train", "eval"}

    @staticmethod
    async def test_a_hit_records_too(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        """A key first seen in an earlier session is recorded again on a hit,
        so a run that only reads the cache still protects what it read."""
        block = (
            "with mo.persistent_cache('train'):\n"
            "    print('computed')\n"
            "    x = 42\n"
        )
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [exec_req.get("import marimo as mo"), exec_req.get(block)]
            )
            assert k.stdout.messages.count("computed") == 1
            written = _manifest(notebook, cache_dir)
        (cache_dir / manifest_name(notebook)).unlink()

        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [exec_req.get("import marimo as mo"), exec_req.get(block)]
            )
            assert not k.stderr.messages
            # The body did not run: only the hit branch can have recorded.
            assert not k.stdout.messages
            assert k.globals["x"] == 42
            assert _entry_keys(_manifest(notebook, cache_dir)) == _entry_keys(
                written
            )

    @staticmethod
    async def test_a_function_hit_records_too(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        source = "@mo.persistent_cache\ndef square(n):\n    return n * n\n"
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(source),
                    exec_req.get("answer = square(7)"),
                ]
            )
            assert not k.stderr.messages
            written = _manifest(notebook, cache_dir)
        (cache_dir / manifest_name(notebook)).unlink()

        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(source),
                    exec_req.get("answer = square(7)"),
                ]
            )
            assert not k.stderr.messages
            assert k.globals["answer"] == 49
            assert k.globals["square"].misses == 0
            assert _entry_keys(_manifest(notebook, cache_dir)) == _entry_keys(
                written
            )

    @staticmethod
    async def test_an_async_hit_records_too(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        source = (
            "@mo.persistent_cache\nasync def square(n):\n    return n * n\n"
        )
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(source),
                    exec_req.get("answer = await square(7)"),
                ]
            )
            assert not k.stderr.messages
            assert k.globals["answer"] == 49
            written = _manifest(notebook, cache_dir)
        (cache_dir / manifest_name(notebook)).unlink()

        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(source),
                    exec_req.get("answer = await square(7)"),
                ]
            )
            assert not k.stderr.messages
            assert k.globals["square"].misses == 0
            assert _entry_keys(_manifest(notebook, cache_dir)) == _entry_keys(
                written
            )

    @staticmethod
    async def test_a_manifest_is_written_once_for_a_run_of_new_keys(
        tmp_path: Path,
        exec_req: ExecReqProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The manifest is rewritten whole, so a cell that fills a cache with
        many keys must not rewrite it once per key, and a rerun that records
        nothing new must not rewrite it at all."""

        def manifest_writes(keys: list[str]) -> int:
            return sum(is_manifest_name(key) for key in keys)

        with _recorded_puts(monkeypatch) as keys:
            with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
                call = exec_req.get(
                    "total = sum(square(n) for n in range(20))"
                )
                await k.run(
                    [
                        exec_req.get("import marimo as mo"),
                        exec_req.get(
                            "@mo.persistent_cache\n"
                            "def square(n):\n"
                            "    return n * n\n"
                        ),
                        call,
                    ]
                )
                assert not k.stderr.messages
                assert len(_entry_keys(_manifest(notebook, cache_dir))) == 20
                assert manifest_writes(keys) == 1

                await k.run([call])
                assert not k.stderr.messages
                assert k.globals["square"].misses == 20
                assert manifest_writes(keys) == 1

    @staticmethod
    async def test_cell_caching_records_its_entries(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        """Whole-cell caching writes entries of its own, under one block."""
        with _notebook_kernel(tmp_path, cache_cells=True) as (
            k,
            notebook,
            cache_dir,
        ):
            await k.run([exec_req.get("x = 42")])
            assert not k.stderr.messages
            entries = _entry_keys(_manifest(notebook, cache_dir))
            assert {block for block, _ in entries} == {"cell_cache"}

    @staticmethod
    async def test_a_restored_cell_records_too(
        tmp_path: Path,
        exec_req: ExecReqProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A session whose cells all restore from disk still records the
        entries it restored from."""
        cell = "x = 42"
        with _notebook_kernel(tmp_path, cache_cells=True) as (
            k,
            notebook,
            cache_dir,
        ):
            await k.run([exec_req.get(cell)])
            written = _manifest(notebook, cache_dir)
        (cache_dir / manifest_name(notebook)).unlink()

        with _recorded_puts(monkeypatch) as keys:
            with _notebook_kernel(tmp_path, cache_cells=True) as (
                k,
                notebook,
                cache_dir,
            ):
                await k.run([exec_req.get(cell)])
                assert not k.stderr.messages
                assert _entry_keys(
                    _manifest(notebook, cache_dir)
                ) == _entry_keys(written)

        # Nothing but the manifest was written: the cell was restored, so only
        # the hit branch can have recorded its entry.
        assert all(is_manifest_name(key) for key in keys)

    @staticmethod
    async def test_repeated_cell_hit_does_not_rewrite_manifest(
        tmp_path: Path,
        exec_req: ExecReqProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        request = exec_req.get("x = 42")
        with _notebook_kernel(tmp_path, cache_cells=True) as (k, _, _):
            await k.run([request])

        with _recorded_puts(monkeypatch) as keys:
            with _notebook_kernel(tmp_path, cache_cells=True) as (
                k,
                notebook,
                cache_dir,
            ):
                await k.run([request])
                assert not k.stderr.messages
                assert k.globals["x"] == 42
                assert keys == [manifest_name(notebook)]
                recorded = _manifest(notebook, cache_dir)
                keys.clear()

                await k.run([request])
                assert not k.stderr.messages
                assert k.globals["x"] == 42
                assert keys == []
                assert _manifest(notebook, cache_dir) == recorded

    @staticmethod
    async def test_teardown_writes_what_a_failed_flush_left_pending(
        tmp_path: Path,
        exec_req: ExecReqProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A store that refuses one write must not lose the record."""
        original_put = FileStore.put
        refused: list[str] = []

        def refuse_first_manifest(
            self: FileStore, key: str, value: bytes
        ) -> bool:
            if is_manifest_name(key) and not refused:
                refused.append(key)
                raise OSError("no space left on device")
            return original_put(self, key, value)

        monkeypatch.setattr(FileStore, "put", refuse_first_manifest)

        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        "with mo.persistent_cache('train'):\n    x = 42\n"
                    ),
                ]
            )
            assert refused
            assert not (cache_dir / manifest_name(notebook)).exists()

        assert _entry_keys(_manifest(notebook, cache_dir))

    @staticmethod
    async def test_a_declined_write_is_a_failed_flush_too(
        tmp_path: Path,
        exec_req: ExecReqProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A store can decline a write by returning False rather than
        raising. The record is kept pending all the same."""
        original_put = FileStore.put
        declined: list[str] = []

        def decline_first_manifest(
            self: FileStore, key: str, value: bytes
        ) -> bool:
            if is_manifest_name(key) and not declined:
                declined.append(key)
                return False
            return original_put(self, key, value)

        monkeypatch.setattr(FileStore, "put", decline_first_manifest)

        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        "with mo.persistent_cache('train'):\n    x = 42\n"
                    ),
                ]
            )
            assert declined
            assert not (cache_dir / manifest_name(notebook)).exists()

        assert _entry_keys(_manifest(notebook, cache_dir))

    @staticmethod
    async def test_a_saved_entry_is_recorded_again_after_a_clean(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        """`marimo cache clean` can take an entry and its record away in the
        middle of a session. A rerun that writes the entry again records
        it again, however often the session saw it before."""
        cell = "with mo.persistent_cache('train'):\n    x = 42\n"
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            cached = exec_req.get(cell)
            await k.run([exec_req.get("import marimo as mo"), cached])
            assert _entry_keys(_manifest(notebook, cache_dir))
            # What `marimo cache clean nb.py` leaves behind.
            shutil.rmtree(cache_dir / "train")
            (cache_dir / manifest_name(notebook)).write_bytes(
                CacheManifest().to_bytes()
            )

            await k.run([exec_req.get_with_id(cached.cell_id, cell)])

            assert _entry_keys(_manifest(notebook, cache_dir))

    @staticmethod
    async def test_a_failed_flush_retries_where_the_entry_lives(
        tmp_path: Path,
        exec_req: ExecReqProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The retry writes the manifest beside the entries it lists, not
        into whichever cache directory the session happens to default to."""
        original_put = FileStore.put
        elsewhere = tmp_path / "elsewhere"
        refused: list[str] = []

        def refuse_first_manifest(
            self: FileStore, key: str, value: bytes
        ) -> bool:
            if is_manifest_name(key) and not refused:
                refused.append(key)
                raise OSError("no space left on device")
            return original_put(self, key, value)

        monkeypatch.setattr(FileStore, "put", refuse_first_manifest)

        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        "with mo.persistent_cache('train', save_path="
                        f"{str(elsewhere)!r}):\n    x = 42\n"
                    ),
                ]
            )
            assert refused

        assert _entry_keys(_manifest(notebook, elsewhere))
        assert not (cache_dir / manifest_name(notebook)).exists()

    @staticmethod
    async def test_each_cache_location_gets_its_own_manifest(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        """A manifest lists only the entries stored beside it. A prune reads
        it as a statement about its own directory."""
        elsewhere = tmp_path / "elsewhere"
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        "with mo.persistent_cache('here'):\n    a = 1\n"
                    ),
                    exec_req.get(
                        "with mo.persistent_cache('there', save_path="
                        f"{str(elsewhere)!r}):\n    b = 2\n"
                    ),
                ]
            )
            assert not k.stderr.messages

            here = _entry_keys(_manifest(notebook, cache_dir))
            there = _entry_keys(_manifest(notebook, elsewhere))
            assert {block for block, _ in here} == {"here"}
            assert {block for block, _ in there} == {"there"}
            for block, key in here | there:
                directory = cache_dir if block == "here" else elsewhere
                assert (directory / block / f"{key}.jsonl").exists()

    @staticmethod
    async def test_every_copy_of_a_manifest_finds_the_notebook(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        """A tiered store puts each entry, manifest included, in every tier.
        The notebook a manifest names has to be reachable from whichever
        directory the copy was read out of."""
        from marimo._save.stores.tiered import TieredStore

        fast = tmp_path / "fast"
        with _notebook_kernel(
            tmp_path,
            store=TieredStore(
                [
                    FileStore(save_path=str(fast)),
                    FileStore(
                        save_path=str(tmp_path / "__marimo__" / "cache")
                    ),
                ]
            ),
        ) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        "with mo.persistent_cache('train'):\n    x = 42\n"
                    ),
                ]
            )
            assert not k.stderr.messages

            for directory in (fast, cache_dir):
                manifest = _manifest(notebook, directory)
                recorded = directory / manifest["notebook"]
                assert recorded.resolve() == notebook.resolve()

    @staticmethod
    async def test_a_corrupt_manifest_is_rewritten(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        """Bytes that read as no manifest list nothing to preserve."""
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / manifest_name(notebook)).write_bytes(b"{not json")
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        "with mo.persistent_cache('train'):\n    x = 42\n"
                    ),
                ]
            )
            assert not k.stderr.messages
            manifest = _manifest(notebook, cache_dir)
            assert manifest["version"] == MANIFEST_VERSION
            assert len(_entry_keys(manifest)) == 1

    @staticmethod
    async def test_a_newer_manifest_is_left_alone(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        """A manifest from a newer marimo holds records under rules this one
        does not know. A rewrite drops them silently."""
        payload = json.dumps(
            {
                "version": MANIFEST_VERSION + 1,
                "nodes": {"3f9c": {"train": ["C_ab12"]}},
            }
        ).encode()
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / manifest_name(notebook)).write_bytes(payload)
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        "with mo.persistent_cache('train'):\n    x = 42\n"
                    ),
                ]
            )
            assert not k.stderr.messages
            assert k.globals["x"] == 42

        assert (cache_dir / manifest_name(notebook)).read_bytes() == payload

    @staticmethod
    async def test_an_unreadable_manifest_does_not_fail_the_cell(
        tmp_path: Path,
        exec_req: ExecReqProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Bookkeeping about a cache must never break the run it happens in."""
        original_read = Path.read_bytes

        def refuse_manifest(self: Path) -> bytes:
            if is_manifest_name(self.name):
                raise PermissionError(f"unreadable: {self.name}")
            return original_read(self)

        monkeypatch.setattr(Path, "read_bytes", refuse_manifest)

        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        "with mo.persistent_cache('train'):\n    x = 42\n"
                    ),
                    exec_req.get("downstream = x + 1"),
                ]
            )
            assert not k.stderr.messages
            assert k.globals["x"] == 42
            assert k.globals["downstream"] == 43
            assert not (cache_dir / manifest_name(notebook)).exists()

    @staticmethod
    async def test_session_cache_records_nothing(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        "@mo.cache\ndef square(n):\n    return n * n\n"
                    ),
                    exec_req.get("answer = square(7)"),
                ]
            )
            assert not k.stderr.messages
            assert k.globals["answer"] == 49
            assert not (cache_dir / manifest_name(notebook)).exists()

    @staticmethod
    async def test_no_manifest_without_a_persistent_event(
        tmp_path: Path, exec_req: ExecReqProvider
    ) -> None:
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run([exec_req.get("x = 42")])
            assert not k.stderr.messages
        assert not (cache_dir / manifest_name(notebook)).exists()

    @staticmethod
    async def test_scratchpad_records_nothing(tmp_path: Path) -> None:
        """A scratchpad cell is in no notebook graph, so no manifest can list
        its entries and prune must never see them."""
        with _notebook_kernel(tmp_path) as (k, notebook, cache_dir):
            await k.run_scratchpad(
                "import marimo as mo\n"
                "with mo.persistent_cache('scratch'):\n"
                "    x = 42\n"
            )
            assert not k.stderr.messages
            # The entry is on disk. Nothing in the notebook records it.
            assert list((cache_dir / "scratch").iterdir())
            assert not (cache_dir / manifest_name(notebook)).exists()


class TestManifestFlush:
    @staticmethod
    @pytest.mark.parametrize("wasm", [False, True])
    @pytest.mark.parametrize("status", [200, 404, 403, 503])
    def test_http_manifest_read(wasm: bool, status: int) -> None:
        store: Store = (
            WasmLazyStore(DictStore())
            if wasm
            else RestStore(
                base_url="https://example.invalid", api_key="test-key"
            )
        )
        manifest = CacheManifest(nodes={"node": {"block": {"C_old"}}})
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = manifest.to_bytes()
        key = "nb-0123456789abcdef.json"
        with patch("urllib.request.urlopen", return_value=response) as request:
            if status != 200:
                request.side_effect = HTTPError(
                    "https://example.invalid", status, "Unavailable", {}, None
                )
            if status in (200, 404):
                loaded = load_manifest(store, key)
                if status == 404:
                    assert loaded is None
                else:
                    assert loaded is not None
                    assert loaded.nodes == manifest.nodes
                    if wasm:
                        assert store.export_keys() == [key]
            else:
                with pytest.raises(HTTPError):
                    load_manifest(store, key)
                assert store.get(key) is None

    @staticmethod
    @pytest.mark.parametrize("wrapped", [False, True])
    def test_each_tier_retains_its_history(
        tmp_path: Path, wrapped: bool
    ) -> None:
        fast = FileStore(str(tmp_path / "fast"))
        slow = FileStore(str(tmp_path / "slow"))
        store: Store = TieredStore([fast, TieredStore([slow])])
        if wrapped:
            store = LazyStore(LazyStore(store))
        with _notebook_kernel(tmp_path, store=store) as (_, notebook, _):
            key = manifest_name(notebook)
            for tier, entry in [(fast, "C_fast"), (slow, "C_slow")]:
                tier.put(
                    key,
                    CacheManifest(
                        nodes={"node": {"block": {entry}}}
                    ).to_bytes(),
                )
            ctx = get_context()
            ctx.cache.manifest_records[store] = {"node": {"block": {"C_new"}}}
            ctx.cache.manifest_dirty.add(store)

            flush_dirty_manifests(ctx)

            for tier, entry in [(fast, "C_fast"), (slow, "C_slow")]:
                manifest = load_manifest(tier, key)
                assert manifest is not None
                assert manifest.nodes == {"node": {"block": {entry, "C_new"}}}
            assert not ctx.cache.manifest_dirty
            if wrapped:
                assert store.export_keys() == [key]

    @staticmethod
    @pytest.mark.parametrize("failure", [403, 503, "connection", "write"])
    def test_failed_read_preserves_history_until_retry(
        tmp_path: Path, failure: int | str
    ) -> None:
        remote = RestStore(
            base_url="https://example.invalid", api_key="test-key"
        )
        local = FileStore(str(tmp_path / "local"))
        store = LazyStore(TieredStore([remote, local]))
        with _notebook_kernel(tmp_path, store=store) as (_, notebook, _):
            key = manifest_name(notebook)
            history = CacheManifest(
                nodes={"node": {"block": {"C_remote"}}}
            ).to_bytes()
            remote_data = {key: history}
            local.put(
                key,
                CacheManifest(
                    nodes={"node": {"block": {"C_local"}}}
                ).to_bytes(),
            )
            ctx = get_context()
            ctx.cache.manifest_records[store] = {"node": {"block": {"C_new"}}}
            ctx.cache.manifest_dirty.add(store)
            failing = True

            def urlopen(request: Any, **_kwargs: Any) -> MagicMock:
                if (
                    failing
                    and failure == "write"
                    and request.get_method() == "PUT"
                ):
                    raise URLError("Connection failed")
                if (
                    request.get_method() == "GET"
                    and failing
                    and failure != "write"
                ):
                    if isinstance(failure, int):
                        raise HTTPError(
                            request.full_url, failure, "Unavailable", {}, None
                        )
                    raise URLError("Connection failed")
                response = MagicMock()
                response.status = 200
                response.__enter__.return_value = response
                if request.get_method() == "PUT":
                    remote_data[key] = request.data
                else:
                    response.read.return_value = remote_data[key]
                return response

            with patch("urllib.request.urlopen", side_effect=urlopen):
                flush_dirty_manifests(ctx)
                assert remote_data[key] == history
                local_manifest = load_manifest(local, key)
                assert local_manifest is not None
                assert local_manifest.nodes == {
                    "node": {"block": {"C_local", "C_new"}}
                }
                assert store in ctx.cache.manifest_dirty

                failing = False
                flush_dirty_manifests(ctx)

            assert CacheManifest.from_bytes(remote_data[key]).nodes == {
                "node": {"block": {"C_remote", "C_new"}}
            }
            assert not ctx.cache.manifest_dirty

    @staticmethod
    def test_newer_tier_is_untouched_while_another_updates(
        tmp_path: Path,
    ) -> None:
        newer = FileStore(str(tmp_path / "newer"))
        current = FileStore(str(tmp_path / "current"))
        store = TieredStore([newer, current])
        payload = json.dumps(
            {
                "version": MANIFEST_VERSION + 1,
                "nodes": {"future": {"block": ["C_old"]}},
            }
        ).encode()
        with _notebook_kernel(tmp_path, store=store) as (_, notebook, _):
            key = manifest_name(notebook)
            newer.put(key, payload)
            ctx = get_context()
            ctx.cache.manifest_records[store] = {"node": {"block": {"C_new"}}}
            ctx.cache.manifest_dirty.add(store)

            flush_dirty_manifests(ctx)

            assert newer.read(key) == payload
            manifest = load_manifest(current, key)
            assert manifest is not None
            assert manifest.nodes == {"node": {"block": {"C_new"}}}
            assert not ctx.cache.manifest_dirty

    @staticmethod
    def test_wasm_checks_all_inner_tiers_before_http(tmp_path: Path) -> None:
        first, second = DictStore(), DictStore()
        store = WasmLazyStore(TieredStore([first, second]))
        with _notebook_kernel(tmp_path, store=store) as (_, notebook, _):
            key = manifest_name(notebook)
            second.put(
                key,
                CacheManifest(nodes={"node": {"block": {"C_old"}}}).to_bytes(),
            )
            ctx = get_context()
            ctx.cache.manifest_records[store] = {"node": {"block": {"C_new"}}}
            ctx.cache.manifest_dirty.add(store)

            with patch(
                "urllib.request.urlopen", side_effect=URLError("Offline")
            ) as request:
                flush_dirty_manifests(ctx)
            request.assert_not_called()

            for tier in (first, second):
                manifest = load_manifest(tier, key)
                assert manifest is not None
                assert manifest.nodes == {
                    "node": {"block": {"C_old", "C_new"}}
                }
            assert not ctx.cache.manifest_dirty
            assert store.export_keys() == [key]

    @staticmethod
    def test_concurrent_flushes_keep_both_writers(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from marimo._utils.file_lock import file_lock

        path = str(tmp_path / "cache")
        first = LazyStore(FileStore(path))
        second = LazyStore(FileStore(path))
        original_read = FileStore.read
        original_put = FileStore.put

        def assert_locked(key: str) -> None:
            with pytest.raises(BlockingIOError):
                with file_lock(Path(path) / f"{key}.lock", blocking=False):
                    pass

        def read(self: FileStore, key: str) -> bytes | None:
            assert_locked(key)
            return original_read(self, key)

        def put(self: FileStore, key: str, value: bytes) -> bool:
            assert_locked(key)
            return original_put(self, key, value)

        with _notebook_kernel(tmp_path) as (_, notebook, _):
            ctx = get_context()
            ctx.cache.manifest_records[first] = {
                "node": {"block": {"C_first"}}
            }
            ctx.cache.manifest_records[second] = {
                "node": {"block": {"C_second"}}
            }
            key = manifest_name(notebook)
            first.put(
                key,
                CacheManifest(nodes={"node": {"block": {"C_old"}}}).to_bytes(),
            )
            start = Barrier(2)

            def flush(store: Store) -> bool:
                start.wait(timeout=30)
                return flush_cache_manifest(ctx, store)

            with (
                monkeypatch.context() as patcher,
                ThreadPoolExecutor(max_workers=2) as pool,
            ):
                patcher.setattr(FileStore, "read", read)
                patcher.setattr(FileStore, "put", put)
                writers = [
                    pool.submit(flush, store) for store in (first, second)
                ]
                for writer in writers:
                    assert writer.result(timeout=30)

            manifest = load_manifest(FileStore(path), key)
            assert manifest is not None
            assert manifest.nodes == {
                "node": {"block": {"C_old", "C_first", "C_second"}}
            }
