# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import contextlib
import signal
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from types import FrameType
    from typing import ClassVar


class SigintHandler:
    """Defer and coalesce SIGINT callbacks without changing OS signal state."""

    # Shared so handlers forwarding to marimo's handler also respect deferral.
    _pending: ClassVar[
        list[tuple[SigintHandler, int, FrameType | None]] | None
    ] = None

    def __init__(
        self, handler: Callable[[int, FrameType | None], None]
    ) -> None:
        self._handler = handler

    def __call__(self, signum: int, frame: FrameType | None) -> None:
        pending = self._pending
        if pending is not None:
            pending[:] = [(self, signum, frame)]
        else:
            self._handler(signum, frame)

    @classmethod
    @contextlib.contextmanager
    def defer(cls) -> Iterator[None]:
        """Replay a pending signal after the outermost main-thread scope."""
        # Signal handlers run on the main thread; worker writes cannot reenter.
        if threading.current_thread() is not threading.main_thread():
            yield
            return

        previous = cls._pending
        pending: list[tuple[SigintHandler, int, FrameType | None]] = []
        try:
            cls._pending = pending
            yield
        finally:
            # Restore before replay: the handler can raise or write again.
            cls._pending = previous
            if pending:
                handler, signum, frame = pending[0]
                handler(signum, frame)


def restore_signals() -> None:
    # Restore the system default signal handlers.
    #
    # The server process may register signal handlers (uvicorn does this),
    # which we definitely don't want! Otherwise a SIGTERM to this process
    # would be rerouted to the server.
    #
    # See https://github.com/tiangolo/fastapi/discussions/7442#discussioncomment-5141007
    signal.set_wakeup_fd(-1)

    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)


def get_signals() -> dict[int, Any]:
    return {
        signal.SIGTERM: signal.getsignal(signal.SIGTERM),
        signal.SIGINT: signal.getsignal(signal.SIGINT),
    }
