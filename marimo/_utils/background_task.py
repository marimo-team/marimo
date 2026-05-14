# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import concurrent.futures
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, final

from marimo import _loggers

if TYPE_CHECKING:
    from typing_extensions import Self

LOGGER = _loggers.marimo_logger()


class AsyncBackgroundTask(ABC):
    def __init__(self) -> None:
        self.task: asyncio.Task[None] | None = None
        self.running: bool = False
        self._startup_event: asyncio.Event = asyncio.Event()
        self._shutdown_event: asyncio.Event = asyncio.Event()

    @abstractmethod
    async def run(self) -> None:
        """
        The main task routine that should be implemented by subclasses.
        This method contains the actual task logic.
        """

    async def startup(self) -> None:
        """
        Optional startup routine that can be implemented by subclasses.
        This method is called before the main task starts.
        """
        return

    async def shutdown(self) -> None:
        """
        Optional shutdown routine that can be implemented by subclasses.
        This method is called after the main task stops.
        """
        return

    async def _task_wrapper(self) -> None:
        """
        Internal wrapper that handles the task lifecycle.
        """
        try:
            await self.startup()
            self._startup_event.set()

            await self.run()
        except Exception as e:
            LOGGER.error(f"Error in task: {e}")
            raise
        finally:
            self.running = False
            await self.shutdown()
            self._shutdown_event.set()

    @final
    def start(self) -> None:
        """
        Starts the background task.
        """
        if self.task is None or self.task.done():
            self.running = True
            self._startup_event.clear()
            self._shutdown_event.clear()
            self.task = asyncio.create_task(self._task_wrapper())

    @final
    async def stop(self, timeout: float | None = None) -> None:
        """
        Stops the background task.

        Args:
            timeout: Maximum time to wait for the task to stop (in seconds)
        """
        if self.task and not self.task.done():
            self.running = False

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(), timeout=timeout
                )
            except asyncio.TimeoutError:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass

    @final
    def stop_sync(self, timeout: float | None = None) -> None:
        """
        Synchronous version of stop that can be called from non-async code.
        """
        # Nothing to drive shutdown for.
        if self.task is None or self.task.done():
            self.running = False
            return

        # Reuse the task's own loop — spinning up a fresh one with
        # ``asyncio.run`` would error on "future attached to a different
        # event loop" the moment we awaited the existing task.
        task_loop = self.task.get_loop()

        # If we're being called from inside the task's own loop thread
        # (e.g. via ``run_in_executor`` or directly from async code), we
        # can't block — calling ``future.result()`` here would deadlock
        # the loop. Fall back to cooperative shutdown.
        try:
            on_task_thread = asyncio.get_running_loop() is task_loop
        except RuntimeError:
            on_task_thread = False

        if on_task_thread:
            self.running = False
            return

        if task_loop.is_running():
            # Task is on another thread's loop. Dispatch the stop
            # coroutine there and block until it completes (honoring
            # ``timeout``).
            future = asyncio.run_coroutine_threadsafe(
                self.stop(timeout), task_loop
            )
            try:
                future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                # Best-effort: ``stop()`` already cancels the task on
                # its own timeout; flag cooperative shutdown too.
                self.running = False
            return

        # Loop exists but isn't running anywhere: drive it directly.
        task_loop.run_until_complete(self.stop(timeout))

    async def wait_for_startup(self, timeout: float | None = None) -> None:
        """
        Waits for the task to start up.

        Args:
            timeout: Maximum time to wait for startup (in seconds)
        """
        await asyncio.wait_for(self._startup_event.wait(), timeout=timeout)

    async def __aenter__(self) -> Self:
        """
        Async context manager entry.
        """
        self.start()
        await self.wait_for_startup()
        return self

    async def __aexit__(
        self, exc_type: Any, exc_val: Any, exc_tb: Any
    ) -> None:
        """
        Async context manager exit.
        """
        await self.stop()
