# Copyright 2026 Marimo. All rights reserved.
"""`cache.loader` selects the default `mo.persistent_cache` loader."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from marimo import App, _loggers
from marimo._config.config import merge_default_config
from marimo._entrypoints.registry import EntryPointRegistry
from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.context import get_context
from marimo._save.cache import CacheState
from marimo._save.loaders import (
    DEFAULT_LOADER,
    JsonLoader,
    LazyLoader,
    LoaderType,
    PickleLoader,
    get_loader_key,
    get_persistent_loader,
    normalize_loader_key,
)
from marimo._save.save import persistent_cache
from marimo._save.stores.file import FileStore
from marimo._types.ids import CellId_t
from tests._runtime._helpers.session import mocked_kernel_session

if TYPE_CHECKING:
    from marimo._save.cache import Cache


def _patch_ctx(monkeypatch, cache: CacheState | None) -> None:
    ctx = None if cache is None else SimpleNamespace(cache=cache)
    monkeypatch.setattr("marimo._save.save.safe_get_context", lambda: ctx)


def _loader_type(cache_context) -> type:
    return type(cache_context._loader())


class FakeLoader(PickleLoader):
    """A third-party loader as a `marimo.cache.loader` entry point would be."""


class BufferedLoader(FakeLoader):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._pending: list[Cache] = []

    def save_cache(self, cache: Cache) -> bool:
        self._pending.append(cache)
        return True

    def flush(self) -> None:
        for cache in self._pending:
            super().save_cache(cache)
        self._pending.clear()


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
        with pytest.raises(ValueError, match="Invalid cache loader 'nope'"):
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
        with pytest.raises(ValueError, match="Invalid cache loader 'fake'"):
            get_persistent_loader("fake", registry)

    def test_persistent_cache_resolves_configured_entry_point(
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

    @pytest.mark.parametrize("method", ["fake", "memory", "missing"])
    def test_persistent_cache_rejects_custom_method(
        self, method: str, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setattr(
            "marimo._save.loaders._LOADER_REGISTRY", _registry(fake=FakeLoader)
        )
        _patch_ctx(
            monkeypatch,
            CacheState(store=FileStore(str(tmp_path)), loader="fake"),
        )
        with pytest.raises(
            ValueError, match=rf"Invalid method {method!r}.*cache\.loader"
        ):
            persistent_cache("ns", method=method)

    @pytest.mark.parametrize(
        ("loader", "expected_loader"),
        [
            ("pickle", PickleLoader),
            ("json", JsonLoader),
            ("lazy", LazyLoader),
            ("fake", FakeLoader),
            ("buffered", BufferedLoader),
        ],
    )
    @pytest.mark.parametrize("form", ["context", "function", "async"])
    async def test_configured_loaders_restore_across_sessions(
        self,
        loader: str,
        expected_loader: LoaderType,
        form: str,
        monkeypatch,
        tmp_path,
    ) -> None:
        monkeypatch.setattr(
            "marimo._save.loaders._LOADER_REGISTRY",
            _registry(fake=FakeLoader, buffered=BufferedLoader),
        )
        user_config = merge_default_config({"cache": {"loader": loader}})
        if form == "context":
            code = (
                f"with mo.persistent_cache('configured', save_path={str(tmp_path)!r}) as cache:\n"
                "    result = {'answer': [42]}\n"
                "was_hit = cache.hit"
            )
        else:
            prefix = "async " if form == "async" else ""
            await_call = "await " if form == "async" else ""
            code = (
                f"@mo.persistent_cache(save_path={str(tmp_path)!r})\n"
                f"{prefix}def cache():\n    return {{'answer': [42]}}\n"
                f"result = {await_call}cache()\n"
                "was_hit = cache.cache_info().hits > 0"
            )
        commands = [
            ExecuteCellCommand(
                cell_id=CellId_t("imports"), code="import marimo as mo"
            ),
            ExecuteCellCommand(
                cell_id=CellId_t("cache"),
                code=code,
            ),
        ]
        for expected_hit in (False, True):
            with mocked_kernel_session(user_config=user_config) as tk:
                await tk.kernel.run(commands)
                assert (
                    type(tk.kernel.globals["cache"].loader) is expected_loader
                )
                assert (
                    tk.kernel.globals["result"],
                    tk.kernel.globals["was_hit"],
                ) == ({"answer": [42]}, expected_hit)

    async def test_embedded_app_inherits_configured_loader(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "marimo._save.loaders._LOADER_REGISTRY", _registry(fake=FakeLoader)
        )
        child = App()

        @child.cell
        def _():
            import marimo as mo

            selected = mo.persistent_cache("child").loader
            return (selected,)

        user_config = merge_default_config({"cache": {"loader": "fake"}})
        with mocked_kernel_session(user_config=user_config):
            result = await child.embed()
            assert type(result.defs["selected"]) is FakeLoader


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

    @pytest.mark.parametrize(
        ("method", "expected_loader"),
        [("pickle", PickleLoader), ("json", JsonLoader), ("lazy", LazyLoader)],
    )
    def test_explicit_method_wins(
        self, method: str, expected_loader: LoaderType, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setattr(
            "marimo._save.loaders._LOADER_REGISTRY", _registry(fake=FakeLoader)
        )
        _patch_ctx(
            monkeypatch,
            CacheState(store=FileStore(str(tmp_path)), loader="fake"),
        )
        assert (
            _loader_type(persistent_cache("ns", method=method))
            is expected_loader
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


@pytest.mark.parametrize("alias", [False, True])
async def test_default_cache_preserves_shared_outputs(alias, tmp_path) -> None:
    commands = [
        ExecuteCellCommand(
            cell_id=CellId_t("imports"), code="import marimo as mo"
        ),
        ExecuteCellCommand(
            cell_id=CellId_t("cache"),
            code=(
                f"with mo.persistent_cache('aliases', save_path={str(tmp_path)!r}) as cache:\n"
                "    a = []\n"
                f"    b = {'a' if alias else '[]'}\n"
                "a.append(1)\n"
                "was_hit = cache.hit"
            ),
        ),
    ]
    for expected_hit in (False, True):
        with mocked_kernel_session() as tk:
            await tk.kernel.run(commands)
            assert (tk.kernel.globals["b"], tk.kernel.globals["was_hit"]) == (
                [1] if alias else [],
                expected_hit,
            )


async def test_default_cache_clear_recomputes(tmp_path) -> None:
    with mocked_kernel_session() as tk:
        tk.ctx.cache.store = FileStore(str(tmp_path))
        await tk.kernel.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t("imports"), code="import marimo as mo"
                ),
                ExecuteCellCommand(
                    cell_id=CellId_t("cache"),
                    code=(
                        "@mo.persistent_cache\n"
                        "def compute():\n    return 42\n"
                        "compute()\ncompute()\n"
                        "before = compute.cache_info()\n"
                        "compute.cache_clear()\n"
                        "result = compute()\n"
                        "after = compute.cache_info()"
                    ),
                ),
            ]
        )
        assert tk.kernel.globals["result"] == 42
        assert tk.kernel.globals["before"].hits == 1
        after = tk.kernel.globals["after"]
        assert (after.hits, after.misses) == (1, 2)
