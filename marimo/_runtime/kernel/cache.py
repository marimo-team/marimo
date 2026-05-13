# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._messaging.notification import (
    CacheClearedNotification,
    CacheInfoNotification,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.context import get_context

if TYPE_CHECKING:
    from marimo._runtime.runtime import Kernel
    from marimo._runtime.commands import ClearCacheCommand, GetCacheInfoCommand

class CacheCallbacks:
    def __init__(self, kernel: Kernel):
        self._kernel = kernel

    async def clear_cache(self, request: ClearCacheCommand) -> None:
        del request
        from marimo._save.cache import CacheContext
        from marimo._save.loaders import BasePersistenceLoader

        ctx = get_context()
        saved = 0
        for obj in ctx.globals.values():
            if isinstance(obj, CacheContext):
                if isinstance(obj.loader, BasePersistenceLoader):
                    obj.loader.clear()

        broadcast_notification(CacheClearedNotification(bytes_freed=saved))

    async def get_cache_info(self, request: GetCacheInfoCommand) -> None:
        del request
        from marimo._save.cache import CacheContext

        ctx = get_context()
        total_hits = 0
        total_misses = 0
        total_time = 0
        disk_to_free = -1  # TODO: sum up disk usage
        disk_total = -1

        for obj in ctx.globals.values():
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
