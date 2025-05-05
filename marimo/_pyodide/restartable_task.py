import asyncio
from typing import Any, Callable, Optional


class RestartableTask:
    def __init__(self, coro: Callable[[], Any]):
        self.coro = coro
        self.task: Optional[asyncio.Task[Any]] = None
        self.stopped = False

    async def start(self) -> None:
        """Create a task that runs the coro."""
        while True:
            if self.stopped:
                break

            try:
                self.task = asyncio.create_task(self.coro())
                await self.task
            except asyncio.CancelledError:
                pass

    def stop(self) -> None:
        # Stop the task and set the stopped flag
        self.stopped = True
        assert self.task is not None
        self.task.cancel()

    def restart(self) -> None:
        # Cancel the current task, which will cause
        # the while loop to start a new task
        assert self.task is not None
        self.task.cancel()
