# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, final

from marimo import _loggers

if TYPE_CHECKING:
    from typing_extensions import Self

LOGGER = _loggers.marimo_logger()


class AsyncBackgroundTask(ABC):
    def __init__(self) -> None:
        self.task: Optional[asyncio.Task[None]] = None
        self.running: bool = False
        self._startup_event: asyncio.Event = asyncio.Event()
        self._shutdown_event: asyncio.Event = asyncio.Event()

    @abstractmethod
    async def run(self) -> None:
        """
        The main task routine that should be implemented by subclasses.
        This method contains the actual task logic.
        """
        pass

    async def startup(self) -> None:
        """
        Optional startup routine that can be implemented by subclasses.
        This method is called before the main task starts.
        """
        return None

    async def shutdown(self) -> None:
        """
        Optional shutdown routine that can be implemented by subclasses.
        This method is called after the main task stops.
        """
        return None

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
    async def stop(self, timeout: Optional[float] = None) -> None:
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
    def stop_sync(self, timeout: Optional[float] = None) -> None:
        """
        Synchronous version of stop that can be called from non-async code.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't run a new event loop while one is running
                # Just set running to false and let the task complete naturally
                self.running = False
                return
            loop.run_until_complete(self.stop(timeout))
        except RuntimeError:
            # If there's no event loop, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.stop(timeout))
            loop.close()

    async def wait_for_startup(self, timeout: Optional[float] = None) -> None:
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
