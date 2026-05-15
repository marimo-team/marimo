# Copyright 2026 Marimo. All rights reserved.
"""Step-controlled driver for `kernel_lifecycle.listen_messages`.

Use `LoopDriver` instead of `await kernel.run(...)` when a test needs to
observe request-by-request behavior (ordering, mid-batch interrupts).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from marimo._runtime.commands import StopKernelCommand
from marimo._runtime.kernel_lifecycle import listen_messages

if TYPE_CHECKING:
    from marimo._runtime.commands import BatchableCommand, CommandMessage
    from marimo._runtime.runtime import Kernel


class LoopDriver:
    """Drive `listen_messages` one request at a time from a test."""

    def __init__(
        self,
        kernel: Kernel,
        control_queue: asyncio.Queue[CommandMessage],
        set_ui_element_queue: asyncio.Queue[BatchableCommand],
    ) -> None:
        self._kernel = kernel
        self._control_queue = control_queue
        self._ui_queue = set_ui_element_queue
        self._task: asyncio.Task[None] | None = None

    def enqueue(self, *requests: CommandMessage) -> None:
        for r in requests:
            self._control_queue.put_nowait(r)

    async def start(self) -> None:
        """Spawn the listen_messages task in the background."""
        assert self._task is None, "LoopDriver already started"

        async def _reader(q: Any) -> Any:
            return await q.get()

        self._task = asyncio.create_task(
            listen_messages(
                self._kernel, self._control_queue, self._ui_queue, _reader
            )
        )

    async def settle(self) -> None:
        """Yield to the event loop until the control queue is drained."""
        while not self._control_queue.empty():  # noqa: ASYNC110
            await asyncio.sleep(0)
        # Extra yield so the in-flight handle_message can complete.
        await asyncio.sleep(0)

    async def stop(self) -> None:
        """Send StopKernelCommand and await the listener's exit."""
        if self._task is None:
            return
        self._control_queue.put_nowait(StopKernelCommand())
        await self._task
        self._task = None
