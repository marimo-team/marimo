# Copyright 2026 Marimo. All rights reserved.
"""Same-interpreter `multiprocessing.Queue` adapters for Pyodide."""

from __future__ import annotations

import asyncio
import queue as _queue
import time
from collections import deque
from typing import TYPE_CHECKING, Any

from marimo._runtime._wasm._concurrency import _state
from marimo._runtime._wasm._concurrency._threading import AsyncEvent
from marimo._runtime._wasm._concurrency._wait import cooperative_wait

if TYPE_CHECKING:
    from multiprocessing.context import BaseContext


_MAIN_PROCESS_OWNER = object()


class AsyncProcessQueue:
    """Store process-shaped queue values in the current interpreter."""

    def __init__(
        self, maxsize: int = 0, *, ctx: BaseContext | None = None
    ) -> None:
        del ctx
        self._maxsize = maxsize
        self._items: deque[Any] = deque()
        self._closed_owners: set[object] = set()
        self._owner_closed_events: dict[object, AsyncEvent] = {}
        self._not_empty = AsyncEvent()
        self._not_full = AsyncEvent()
        self._sync_events()

    def _full(self) -> bool:
        return self._maxsize > 0 and len(self._items) >= self._maxsize

    def _sync_events(self) -> None:
        if self._items:
            self._not_empty.set()
        else:
            self._not_empty.clear()

        if self._full():
            self._not_full.clear()
        else:
            self._not_full.set()

    def _check_open(self) -> None:
        if _current_owner() in self._closed_owners:
            raise ValueError("Queue is closed")

    def _owner_closed_event(self, owner: object) -> AsyncEvent:
        return self._owner_closed_events.setdefault(owner, AsyncEvent())

    async def _wait_until_not_full(self, timeout: float | None) -> bool:
        end_time = None if timeout is None else time.monotonic() + timeout
        owner = _current_owner()
        closed_event = self._owner_closed_event(owner)
        while self._full():
            if owner in self._closed_owners:
                return True
            remaining = None
            if end_time is not None:
                remaining = end_time - time.monotonic()
                if remaining <= 0:
                    return False
            if not await _wait_for_queue_or_owner_close(
                self._not_full,
                closed_event,
                remaining,
            ):
                return False
        return True

    async def _wait_until_not_empty(self, timeout: float | None) -> bool:
        end_time = None if timeout is None else time.monotonic() + timeout
        owner = _current_owner()
        closed_event = self._owner_closed_event(owner)
        while not self._items:
            if owner in self._closed_owners:
                return True
            remaining = None
            if end_time is not None:
                remaining = end_time - time.monotonic()
                if remaining <= 0:
                    return False
            if not await _wait_for_queue_or_owner_close(
                self._not_empty,
                closed_event,
                remaining,
            ):
                return False
        return True

    def put(
        self,
        obj: Any,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        self._check_open()
        timeout = _normalize_timeout(timeout)
        while self._full():
            self._check_open()
            if not block or timeout == 0:
                raise _queue.Full
            if not cooperative_wait(self._wait_until_not_full(timeout)):
                raise _queue.Full
        self._check_open()
        self._items.append(obj)
        self._sync_events()

    def put_nowait(self, obj: Any) -> None:
        self.put(obj, block=False)

    def get(
        self,
        block: bool = True,
        timeout: float | None = None,
    ) -> Any:
        self._check_open()
        timeout = _normalize_timeout(timeout)
        while not self._items:
            self._check_open()
            if not block or timeout == 0:
                raise _queue.Empty
            if not cooperative_wait(self._wait_until_not_empty(timeout)):
                raise _queue.Empty
        self._check_open()
        return self._pop()

    def get_nowait(self) -> Any:
        return self.get(block=False)

    def _pop(self) -> Any:
        item = self._items.popleft()
        self._sync_events()
        return item

    def empty(self) -> bool:
        self._check_open()
        return not self._items

    def full(self) -> bool:
        self._check_open()
        return self._full()

    def qsize(self) -> int:
        self._check_open()
        return len(self._items)

    def close(self) -> None:
        owner = _current_owner()
        self._closed_owners.add(owner)
        self._owner_closed_event(owner).set()

    def join_thread(self) -> None:
        return None

    def cancel_join_thread(self) -> None:
        return None


class AsyncProcessSimpleQueue:
    """Store `SimpleQueue` object references in the current interpreter."""

    def __init__(self, *, ctx: BaseContext | None = None) -> None:
        del ctx
        self._items: deque[Any] = deque()
        self._closed_owners: set[object] = set()
        self._owner_closed_events: dict[object, AsyncEvent] = {}
        self._not_empty = AsyncEvent()
        self._sync_events()

    def _check_open(self) -> None:
        if _current_owner() in self._closed_owners:
            raise ValueError("Queue is closed")

    def _owner_closed_event(self, owner: object) -> AsyncEvent:
        return self._owner_closed_events.setdefault(owner, AsyncEvent())

    def put(self, obj: Any) -> None:
        self._check_open()
        self._items.append(obj)
        self._sync_events()

    def get(self) -> Any:
        self._check_open()
        owner = _current_owner()
        closed_event = self._owner_closed_event(owner)
        while not self._items:
            self._check_open()
            cooperative_wait(
                _wait_for_queue_or_owner_close(
                    self._not_empty,
                    closed_event,
                    None,
                )
            )
        self._check_open()
        item = self._items.popleft()
        self._sync_events()
        return item

    def empty(self) -> bool:
        self._check_open()
        return not self._items

    def close(self) -> None:
        owner = _current_owner()
        self._closed_owners.add(owner)
        self._owner_closed_event(owner).set()

    def _sync_events(self) -> None:
        if self._items:
            self._not_empty.set()
        else:
            self._not_empty.clear()


def queue_factory(
    _ctx: BaseContext | None = None,
    maxsize: int = 0,
) -> AsyncProcessQueue:
    return AsyncProcessQueue(maxsize=maxsize, ctx=_ctx)


def simple_queue_factory(
    _ctx: BaseContext | None = None,
) -> AsyncProcessSimpleQueue:
    return AsyncProcessSimpleQueue(ctx=_ctx)


def direct_queue_factory(maxsize: int = 0) -> AsyncProcessQueue:
    return AsyncProcessQueue(maxsize=maxsize)


def direct_simple_queue_factory() -> AsyncProcessSimpleQueue:
    return AsyncProcessSimpleQueue()


def _current_owner() -> object:
    owner = _state.current_process_owner()
    if owner is None:
        return _MAIN_PROCESS_OWNER
    return owner


async def _wait_for_queue_or_owner_close(
    queue_event: AsyncEvent,
    owner_closed_event: AsyncEvent,
    timeout: float | None,
) -> bool:
    if queue_event.is_set() or owner_closed_event.is_set():
        return True

    queue_task = asyncio.create_task(queue_event._wait(None))
    close_task = asyncio.create_task(owner_closed_event._wait(None))
    tasks = (queue_task, close_task)
    try:
        done, _pending = await asyncio.wait(
            tasks,
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            return queue_event.is_set() or owner_closed_event.is_set()
        return True
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def _normalize_timeout(timeout: float | None) -> float | None:
    if timeout is not None and timeout < 0:
        return 0
    return timeout
