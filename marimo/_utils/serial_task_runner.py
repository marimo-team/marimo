# Copyright 2026 Marimo. All rights reserved.
"""FIFO dispatch of blocking work off the asyncio event loop.

Usage::

    runner = SerialTaskRunner(thread_name_prefix="autosave")
    runner.submit(
        lambda: file_manager.save_from_cells(cells),
        on_error=lambda err: session.notify(AlertNotification(...)),
    )
    runner.shutdown()  # on session close
    await runner.drain()  # in async tests

``submit`` and ``shutdown`` must be called from the asyncio event loop
thread (or from any thread when no loop is running). ``work`` runs on
the executor thread; ``on_error`` is routed back to the loop thread via
``call_soon_threadsafe`` so it can safely touch asyncio primitives.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property
from typing import TYPE_CHECKING, Any

from marimo import _loggers

if TYPE_CHECKING:
    from collections.abc import Callable

LOGGER = _loggers.marimo_logger()


class SerialTaskRunner:
    """FIFO-ordered dispatch of blocking work to a dedicated worker thread."""

    def __init__(self, *, thread_name_prefix: str = "serial-task") -> None:
        self._thread_name_prefix = thread_name_prefix
        self._pending: list[asyncio.Future[Any]] = []

    @cached_property
    def _executor(self) -> ThreadPoolExecutor:
        return ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=self._thread_name_prefix
        )

    @property
    def pending(self) -> list[asyncio.Future[Any]]:
        """In-flight futures; tests can await these to synchronize."""
        return self._pending

    def submit(
        self,
        work: Callable[[], None],
        *,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        """Run ``work()`` on the serial worker thread.

        Offloads to the executor when called from the event loop;
        otherwise runs inline on the caller thread (e.g. the
        ``QueueDistributor`` worker thread). ``on_error`` is invoked
        with any exception raised by ``work`` — posted back to the event
        loop when off-loop, inline otherwise. A failing ``on_error`` is
        logged and swallowed.
        """
        try:
            loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        def _run() -> None:
            try:
                work()
            except Exception as err:
                self._handle_error(loop, on_error, err)

        if loop is None:
            _run()
            return

        fut = loop.run_in_executor(self._executor, _run)
        # Prune done futures so the list stays bounded over long sessions.
        self._pending[:] = [f for f in self._pending if not f.done()]
        self._pending.append(fut)

    @staticmethod
    def _handle_error(
        loop: asyncio.AbstractEventLoop | None,
        on_error: Callable[[Exception], None] | None,
        err: Exception,
    ) -> None:
        if on_error is None:
            LOGGER.error(
                "SerialTaskRunner task failed with no on_error handler: %s",
                err,
                exc_info=err,
            )
            return

        def _safe_on_error() -> None:
            try:
                on_error(err)
            except Exception as handler_err:
                LOGGER.error(
                    "SerialTaskRunner on_error callback failed: %s",
                    handler_err,
                    exc_info=handler_err,
                )

        if loop is None:
            _safe_on_error()
        else:
            loop.call_soon_threadsafe(_safe_on_error)

    async def drain(self) -> None:
        """Await every in-flight task, then clear the pending list.

        ``return_exceptions=True`` so a failing task doesn't abort the drain.
        """
        if not self._pending:
            return
        await asyncio.gather(*self._pending, return_exceptions=True)
        self._pending.clear()

    def shutdown(self, *, wait: bool = False) -> None:
        """Tear down the executor. Idempotent; no-op if never materialized.

        Uses ``__dict__.pop`` so we don't trigger the ``cached_property``
        just to shut it down.
        """
        executor = self.__dict__.pop("_executor", None)
        if executor is not None:
            executor.shutdown(wait=wait)
