# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from marimo import _loggers
from marimo._messaging.notification import (
    CacheClearedNotification,
    CacheInfoNotification,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.commands import ClearCacheCommand, GetCacheInfoCommand

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from typing import Any

    from marimo._config.config import MarimoConfig
    from marimo._runtime.callbacks.protocol import GlobalsView
    from marimo._runtime.request_router import RequestRouter
    from marimo._save.cache import CacheContext
    from marimo._save.loaders.loader import Loader

LOGGER = _loggers.marimo_logger()


def _cache_loader(context: CacheContext) -> Loader | None:
    """The loader `context` reads and writes through, if one is bound yet.

    A decorator not yet applied to a function is a cache in the notebook's
    globals with nothing behind it.
    """
    try:
        return context.loader
    except Exception:
        return None


def cache_cells_enabled(user_config: MarimoConfig) -> bool:
    """Whether `[tool.marimo.runtime] cache_cells` is on (default `False`)."""
    runtime = cast("Mapping[str, Any]", user_config.get("runtime", {}))
    return bool(runtime.get("cache_cells", False))


class CacheCallbacks:
    def __init__(
        self,
        scope: GlobalsView,
        *,
        caching_enabled: Callable[[], bool] | None = None,
        notebook_filename: str | None = None,
    ) -> None:
        self._scope = scope
        # NB. read live at teardown — the config can change mid-session.
        self._caching_enabled = caching_enabled or (lambda: False)
        self._notebook_filename = notebook_filename

    def register(self, router: RequestRouter) -> None:
        router.register(ClearCacheCommand, self.clear_cache)
        router.register(GetCacheInfoCommand, self.get_cache_info)

    def teardown(self) -> None:
        """Flush pending cache writes; publish an export manifest if caching."""
        from marimo._save.loaders import (
            dump_cache_manifests,
            flush_active_caches,
        )
        from marimo._save.stores.file import export_manifest_name

        # NB. flush unconditionally (durability); joins background blob writes.
        flush_active_caches()
        # NB. manifest only when cell caching is on (html-wasm --execute), else
        # a normal session would litter cache dirs with manifests.
        if self._caching_enabled():
            dump_cache_manifests(export_manifest_name(self._notebook_filename))

    async def clear_cache(self, request: ClearCacheCommand) -> None:
        del request
        from marimo._save.cache import CacheContext

        saved = 0
        for obj in self._scope.globals.values():
            if isinstance(obj, CacheContext):
                obj.loader.clear()

        broadcast_notification(CacheClearedNotification(bytes_freed=saved))

    def _disk_usage(self, loaders: list[Loader]) -> tuple[int, int]:
        """Bytes the caches in scope hold, and bytes a purge frees.

        Every number comes from the loaders themselves rather than from a
        directory derived from the notebook path, so a cache configured to
        write somewhere else is measured where it actually writes, and a
        same-named directory it does not use is left out. The two differ
        because a cache directory also holds caches this session never
        loaded, which purging leaves alone. Measuring is best-effort. An
        unreadable or unwritten cache reports zero rather than failing the
        request.
        """
        try:
            from marimo._save.cache_dirs import cache_dir_stats

            cache_dirs = {
                directory
                for loader in loaders
                if (directory := loader.storage_dir()) is not None
            }
            return (
                sum(
                    cache_dir_stats(directory).total_bytes
                    for directory in cache_dirs
                ),
                sum(loader.clearable_bytes() for loader in loaders),
            )
        except Exception:
            LOGGER.debug("Could not measure cache disk usage", exc_info=True)
            return 0, 0

    async def get_cache_info(self, request: GetCacheInfoCommand) -> None:
        del request
        from marimo._save.cache import CacheContext

        total_hits = 0
        total_misses = 0
        total_time = 0.0
        # Keyed by identity. One loader reached through several names is one
        # cache, and its bytes must not be counted once per name.
        loaders: dict[int, Loader] = {}

        for obj in self._scope.globals.values():
            if isinstance(obj, CacheContext):
                hits, misses, _, _, time = obj.cache_info()
                total_hits += hits
                total_misses += misses
                total_time += time
                loader = _cache_loader(obj)
                if loader is not None:
                    loaders[id(loader)] = loader

        disk_total, disk_to_free = self._disk_usage(list(loaders.values()))
        broadcast_notification(
            CacheInfoNotification(
                hits=total_hits,
                misses=total_misses,
                time=total_time,
                disk_to_free=disk_to_free,
                disk_total=disk_total,
            ),
        )
