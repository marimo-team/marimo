# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING

from marimo._messaging.agents import SendResult

if TYPE_CHECKING:
    from collections.abc import Callable


class SendFuture(Future[SendResult]):
    """A standard future with the Message ID available before completion.

    Cancelling a queued send prevents dispatch. Once running, cancellation
    cannot stop delivery. A timeout on `result()` only stops that wait.

    Args:
        message_id (str): Identity of this send.
    """

    def __init__(self, message_id: str) -> None:
        super().__init__()
        self._message_id = message_id

    @property
    def message_id(self) -> str:
        """Identity shared by the pending send and its result."""
        return self._message_id


class _SendQueue:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="marimo-agent-dispatch"
        )

    def submit(
        self, future: SendFuture, send: Callable[[], SendResult]
    ) -> None:
        from marimo._runtime.threads import Thread

        def run() -> None:
            try:
                result = send()
            except BaseException as error:
                future.set_exception(error)
            else:
                future.set_result(result)

        # Capture each caller's cell context before queueing the work.
        thread = Thread(target=run, daemon=True, name="marimo-agent-send")

        def dispatch() -> None:
            if not future.set_running_or_notify_cancel():
                return
            try:
                thread.start()
                # Keep the slot until the marimo thread has fully exited.
                thread.join()
            except Exception as error:
                future.set_exception(error)

        self._executor.submit(dispatch)


send_queue = _SendQueue()
