# Copyright 2026 Marimo. All rights reserved.
"""The manifest format, and the runtime paths that write into it."""

from __future__ import annotations

import contextlib
import copy
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from marimo._config.config import DEFAULT_CONFIG
from marimo._save.manifest import (
    MANIFEST_VERSION,
    CacheManifest,
    CorruptManifestError,
    UnsupportedManifestVersionError,
    load_manifest,
    manifest_name,
)
from marimo._save.stores.file import FileStore
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
    def test_load_manifest_reads_what_flush_wrote(tmp_path: Path) -> None:
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
            assert (cache_dir / block / f"{key}.pickle").exists()

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
                assert (directory / block / f"{key}.pickle").exists()

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
        original_get = FileStore.get

        def refuse_manifest(self: FileStore, key: str) -> bytes | None:
            if is_manifest_name(key):
                raise PermissionError(f"unreadable: {key}")
            return original_get(self, key)

        monkeypatch.setattr(FileStore, "get", refuse_manifest)

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
