# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path

from marimo._save.cache import MARIMO_CACHE_VERSION, Cache
from marimo._save.hash import HashKey
from marimo._save.loaders import LazyLoader
from marimo._save.loaders.lazy import maybe_update_lazy_stub
from marimo._save.stubs.lazy_stub import (
    BLOB_DESERIALIZERS,
    BLOB_SERIALIZERS,
    BlobAsset,
)
from tests._save.store.mocks import MockStore


def test_blob_asset_resolves_to_bin_codec() -> None:
    asset = BlobAsset(
        data=b"<svg></svg>",
        media_type="image/svg+xml",
        filename="chart.svg",
    )

    assert maybe_update_lazy_stub(asset) == "bin"


def test_blob_asset_codec_round_trip() -> None:
    asset = BlobAsset(
        data=b'{"ok": true}',
        media_type="application/json",
        filename="data.json",
        metadata={"format_id": "example.json.v1"},
    )

    encoded = BLOB_SERIALIZERS["bin"](asset)

    assert BLOB_DESERIALIZERS[".bin"](encoded, None) == asset


def test_lazy_loader_round_trips_blob_asset() -> None:
    store = MockStore()
    loader = LazyLoader("asset-test", store=store, mode="off")
    asset = BlobAsset(
        data=b"\x89PNG\r\n\x1a\n",
        media_type="image/png",
        filename="preview.png",
        metadata={"format_id": "image.png.v1"},
    )
    cache = Cache(
        defs={"preview": asset},
        hash="asset_hash",
        cache_type="Pure",
        stateful_refs=set(),
        hit=False,
        meta={"version": MARIMO_CACHE_VERSION, "return": asset},
    )

    assert loader.save_cache(cache)
    loader.flush()

    assert (
        Path("asset-test") / "asset_hash" / "preview.bin"
    ).as_posix() in store._cache
    assert (
        Path("asset-test") / "asset_hash" / "return.bin"
    ).as_posix() in store._cache
    loaded = loader.load_cache(HashKey("asset_hash", "Pure"))

    assert loaded is not None
    assert loaded.defs == {"preview": asset}
    assert loaded.meta["return"] == asset
