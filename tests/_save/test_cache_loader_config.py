# Copyright 2026 Marimo. All rights reserved.
"""`cache.loader` selects the default `mo.persistent_cache` loader."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from marimo import _loggers
from marimo._config.config import merge_default_config
from marimo._entrypoints.registry import EntryPointRegistry
from marimo._runtime.context import get_context
from marimo._save.cache import CacheState
from marimo._save.loaders import (
    DEFAULT_LOADER,
    LazyLoader,
    LoaderType,
    PickleLoader,
    get_loader_key,
    get_persistent_loader,
    normalize_loader_key,
)
from marimo._save.save import persistent_cache
from marimo._save.stores.file import FileStore
from tests._runtime._helpers.session import mocked_kernel_session


def _patch_ctx(monkeypatch, cache: CacheState | None) -> None:
    ctx = None if cache is None else SimpleNamespace(cache=cache)
    monkeypatch.setattr("marimo._save.save.safe_get_context", lambda: ctx)


def _loader_type(cache_context) -> type:
    return type(cache_context._loader())


class FakeLoader(PickleLoader):
    """A third-party loader as a `marimo.cache.loader` entry point would be."""


def _registry(**loaders: object) -> EntryPointRegistry[LoaderType]:
    registry = EntryPointRegistry[LoaderType]("marimo.cache.loader")
    for name, loader in loaders.items():
        registry.register(name, loader)  # type: ignore[arg-type]
    return registry


class TestNormalizeLoaderKey:
    def test_unset_is_lazy(self) -> None:
        assert DEFAULT_LOADER == "lazy"
        assert normalize_loader_key(None) == "lazy"

    @pytest.mark.parametrize("key", ["pickle", "json", "lazy"])
    def test_persistent_keys_pass_through(self, key: str) -> None:
        assert normalize_loader_key(key) == key

    @pytest.mark.parametrize("raw", ["memory", {"type": "lazy"}, 3])
    def test_invalid_value_warns_and_falls_back(
        self, raw: object, caplog: pytest.LogCaptureFixture, monkeypatch
    ) -> None:
        # The marimo logger does not propagate, so caplog needs it to.
        monkeypatch.setattr(_loggers.marimo_logger(), "propagate", True)
        with caplog.at_level(logging.WARNING):
            assert normalize_loader_key(raw) == "lazy"
        assert f"Invalid cache.loader {raw!r}" in caplog.text


class TestEntryPointLoaders:
    def test_registered_name_is_a_valid_key(self) -> None:
        registry = _registry(fake=FakeLoader)
        assert normalize_loader_key("fake", registry) == "fake"
        assert get_persistent_loader("fake", registry) is FakeLoader

    def test_builtin_name_wins_over_entry_point(self) -> None:
        registry = _registry(pickle=FakeLoader)
        assert get_persistent_loader("pickle", registry) is PickleLoader

    def test_unknown_name_raises(self) -> None:
        registry = _registry(fake=FakeLoader)
        with pytest.raises(ValueError, match="Invalid method 'nope'"):
            get_persistent_loader("nope", registry)

    def test_non_loader_entry_point_raises(self) -> None:
        registry = _registry(bad=object)
        with pytest.raises(ValueError, match="must be a Loader subclass"):
            get_persistent_loader("bad", registry)

    def test_allowlist_env_hides_entry_point(
        self, monkeypatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("MARIMO_CACHE_LOADER_ALLOWLIST", "")
        registry = _registry(fake=FakeLoader)
        monkeypatch.setattr(_loggers.marimo_logger(), "propagate", True)
        with caplog.at_level(logging.WARNING):
            assert normalize_loader_key("fake", registry) == "lazy"
        assert "Invalid cache.loader 'fake'" in caplog.text
        with pytest.raises(ValueError, match="Invalid method 'fake'"):
            get_persistent_loader("fake", registry)

    def test_persistent_cache_resolves_entry_point(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setattr(
            "marimo._save.loaders._LOADER_REGISTRY", _registry(fake=FakeLoader)
        )
        _patch_ctx(
            monkeypatch,
            CacheState(store=FileStore(str(tmp_path)), loader="fake"),
        )
        assert _loader_type(persistent_cache("ns")) is FakeLoader
        assert (
            _loader_type(persistent_cache("ns", method="fake")) is FakeLoader
        )


class TestGetLoaderKey:
    def test_reads_cache_loader(self) -> None:
        assert (
            get_loader_key(config={"cache": {"loader": "pickle"}}) == "pickle"
        )

    def test_missing_section_is_default(self) -> None:
        assert get_loader_key(config={}) == "lazy"
        assert get_loader_key(config={"cache": {}}) == "lazy"


class TestPersistentCacheDefaultMethod:
    def test_configured_loader_is_used(self, monkeypatch, tmp_path) -> None:
        _patch_ctx(
            monkeypatch,
            CacheState(store=FileStore(str(tmp_path)), loader="pickle"),
        )
        assert _loader_type(persistent_cache("ns")) is PickleLoader

    def test_explicit_method_wins(self, monkeypatch, tmp_path) -> None:
        _patch_ctx(
            monkeypatch,
            CacheState(store=FileStore(str(tmp_path)), loader="pickle"),
        )
        assert (
            _loader_type(persistent_cache("ns", method="lazy")) is LazyLoader
        )

    def test_no_context_is_lazy(self, monkeypatch) -> None:
        _patch_ctx(monkeypatch, None)
        assert _loader_type(persistent_cache("ns")) is LazyLoader

    def test_cache_state_default_is_lazy(self, tmp_path) -> None:
        assert CacheState(store=FileStore(str(tmp_path))).loader == "lazy"


def test_kernel_reads_cache_loader_from_user_config() -> None:
    user_config = merge_default_config({"cache": {"loader": "pickle"}})
    with mocked_kernel_session(user_config=user_config):
        assert get_context().cache.loader == "pickle"
