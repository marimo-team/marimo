# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._messaging.notification import CacheClearedNotification
from marimo._runtime.commands import ClearCacheCommand
from marimo._save.cache import CacheContext
from marimo._save.loaders.memory import MemoryLoader

if TYPE_CHECKING:
    from tests.conftest import MockedKernel


class _RecordingMemoryLoader(MemoryLoader):
    def __init__(self) -> None:
        super().__init__("test")
        self.cleared = False

    def clear(self) -> None:
        self.cleared = True
        super().clear()


class _StubCacheContext(CacheContext):
    def __init__(self, loader: MemoryLoader) -> None:
        # CacheContext.loader calls self._loader(); wrap in a zero-arg callable.
        self._loader = lambda: loader  # type: ignore[assignment]

    @property
    def last_hash(self) -> str | None:
        return None


class TestClearCache:
    async def test_clears_memory_loaders(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        memory_loader = _RecordingMemoryLoader()
        k.globals["_cache_a"] = _StubCacheContext(memory_loader)

        await k.handle_message(ClearCacheCommand())

        assert memory_loader.cleared is True
        notifications = [
            op
            for op in stream.operations
            if isinstance(op, CacheClearedNotification)
        ]
        assert len(notifications) == 1
