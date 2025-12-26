# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Awaitable, Coroutine
from pathlib import Path
from typing import Callable, Optional

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils import async_path

LOGGER = _loggers.marimo_logger()

Callback = Callable[[Path], Coroutine[None, None, None]]


class FileWatcher(ABC):
    @staticmethod
    def create(path: Path, callback: Callback) -> FileWatcher:
        if DependencyManager.watchdog.has():
            LOGGER.debug("Using watchdog file watcher")
            return _create_watchdog(path, callback, asyncio.get_event_loop())
        else:
            LOGGER.info(
                "watchdog is not installed, using polling file watcher"
            )
            return PollingFileWatcher(path, callback, asyncio.get_event_loop())

    def __init__(
        self,
        path: Path,
        callback: Callback,
    ):
        self.path = path
        self.callback = callback

    async def on_file_changed(self) -> None:
        LOGGER.debug(f"File at {self.path} was modified.")
        await self.callback(self.path)

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass


class PollingFileWatcher(FileWatcher):
    POLL_SECONDS = 1.0  # Poll every 1s

    def __init__(
        self,
        path: Path,
        callback: Callback,
        loop: asyncio.AbstractEventLoop,
    ):
        super().__init__(path, callback)
        self._running = False
        self.loop = loop
        self.last_modified: Optional[float] = self._get_modified()

    def start(self) -> None:
        self._running = True
        self.loop.create_task(self._poll())

    def stop(self) -> None:
        self._running = False

    def _get_modified(self) -> Optional[float]:
        try:
            return os.path.getmtime(self.path)
        except FileNotFoundError:
            return None

    async def _poll(self) -> None:
        while self._running:
            if not await async_path.exists(self.path):
                LOGGER.warning(f"File at {self.path} does not exist.")
                raise FileNotFoundError(f"File at {self.path} does not exist.")

            # Check for file changes
            modified = self._get_modified()
            if self.last_modified is None:
                self.last_modified = modified
            elif modified != self.last_modified:
                self.last_modified = modified
                await self.on_file_changed()
            await asyncio.sleep(self.POLL_SECONDS)


def _create_watchdog(
    path: Path, callback: Callback, loop: asyncio.AbstractEventLoop
) -> FileWatcher:
    import watchdog.events  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501
    import watchdog.observers  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

    class WatchdogFileWatcher(FileWatcher):
        def __init__(
            self,
            path: Path,
            callback: Callback,
            loop: asyncio.AbstractEventLoop,
        ):
            super().__init__(path, callback)
            self.loop = loop
            self.observer = watchdog.observers.Observer()

        def on_modified(
            self,
            event: watchdog.events.FileModifiedEvent
            | watchdog.events.DirModifiedEvent,
        ) -> None:
            del event
            self.loop.create_task(self.on_file_changed())

        def on_moved(
            self,
            event: watchdog.events.FileMovedEvent
            | watchdog.events.DirMovedEvent,
        ) -> None:
            # Handle editors that save by creating a temp file and moving it
            # (e.g., Claude Code, some vim configurations)
            dest_path_str = (
                event.dest_path
                if isinstance(event.dest_path, str)
                else event.dest_path.decode("utf-8")
            )

            if self.path == Path(dest_path_str):
                self.loop.create_task(self.on_file_changed())

        def start(self) -> None:
            event_handler = watchdog.events.PatternMatchingEventHandler(  # type: ignore # noqa: E501
                patterns=[str(self.path)]
            )
            event_handler.on_modified = self.on_modified  # type: ignore
            event_handler.on_moved = self.on_moved  # type: ignore
            self.observer.schedule(  # type: ignore
                event_handler,
                str(self.path.parent),
                recursive=False,
            )
            self.observer.start()  # type: ignore

        def stop(self) -> None:
            self.observer.stop()  # type: ignore
            self.observer.join()

    return WatchdogFileWatcher(path, callback, loop)


FileCallback = Callable[[Path], Awaitable[None]]


class FileWatcherManager:
    """Manages multiple file watchers, sharing watchers for the same file."""

    def __init__(self) -> None:
        # Map of file paths to their watchers
        self._watchers: dict[str, FileWatcher] = {}
        # Map of file paths to their callbacks
        self._callbacks: dict[str, set[FileCallback]] = defaultdict(set)

    def add_callback(self, path: Path, callback: FileCallback) -> None:
        """Add a callback for a file path. Creates watcher if needed."""
        path_str = str(path)
        self._callbacks[path_str].add(callback)

        if path_str not in self._watchers:

            async def shared_callback(changed_path: Path) -> None:
                callbacks = self._callbacks.get(str(changed_path), set())
                # Iterate over a copy to avoid "Set changed size during iteration"
                # if a callback modifies the callbacks set
                for cb in list(callbacks):
                    await cb(changed_path)

            watcher = FileWatcher.create(path, shared_callback)
            watcher.start()
            self._watchers[path_str] = watcher
            LOGGER.debug(f"Created new watcher for {path_str}")

    def remove_callback(self, path: Path, callback: FileCallback) -> None:
        """Remove a callback for a file path. Removes watcher if no more callbacks."""
        path_str = str(path)
        if path_str not in self._callbacks:
            # May already be removed from stop_all()
            return

        self._callbacks[path_str].discard(callback)

        if not self._callbacks[path_str]:
            # No more callbacks, clean up
            del self._callbacks[path_str]
            if path_str in self._watchers:
                self._watchers[path_str].stop()
                del self._watchers[path_str]
                LOGGER.debug(f"Removed watcher for {path_str}")

    def stop_all(self) -> None:
        """Stop all file watchers."""
        for watcher in self._watchers.values():
            watcher.stop()
        self._watchers.clear()
        self._callbacks.clear()
