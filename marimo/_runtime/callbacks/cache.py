# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, cast

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


def cache_cells_enabled(user_config: MarimoConfig) -> bool:
    """Whether cell-level caching (`[tools.runtime.cache_cells]`) is on.

    Read via a plain mapping so it degrades to `False` when the key is absent
    (the setting is introduced alongside the caching lifecycle).
    """
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
        # Read live at teardown (the config can change mid-session); default
        # off so a bare callback never publishes a manifest.
        self._caching_enabled = caching_enabled or (lambda: False)
        self._notebook_filename = notebook_filename

    def register(self, router: RequestRouter) -> None:
        router.register(ClearCacheCommand, self.clear_cache)
        router.register(GetCacheInfoCommand, self.get_cache_info)

    def teardown(self) -> None:
        """Flush pending cache writes, and publish an export manifest.

        Loaders dispatch blob writes to background threads; flushing joins
        them so every blob lands on disk before the session tears down — done
        unconditionally for durability. When cell caching is enabled (which
        `html-wasm --execute` turns on), also record the export manifest an
        executed export bundles from; otherwise a normal session would litter
        cache dirs with manifests.
        """
        from marimo._save.loaders import (
            dump_cache_manifests,
            flush_active_caches,
        )
        from marimo._save.stores.file import export_manifest_name

        flush_active_caches()
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

    async def get_cache_info(self, request: GetCacheInfoCommand) -> None:
        del request
        from marimo._save.cache import CacheContext

        total_hits = 0
        total_misses = 0
        total_time = 0
        disk_to_free = -1  # TODO: sum up disk usage
        disk_total = -1

        for obj in self._scope.globals.values():
            if isinstance(obj, CacheContext):
                hits, misses, _, _, time = obj.cache_info()
                total_hits += hits
                total_misses += misses
                total_time += time
                # d2f, dt = obj.loader.disk_usage()

        broadcast_notification(
            CacheInfoNotification(
                hits=total_hits,
                misses=total_misses,
                time=total_time,
                disk_to_free=disk_to_free,
                disk_total=disk_total,
            ),
        )
