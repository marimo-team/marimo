# Copyright 2026 Marimo. All rights reserved.
"""Ordered events with subscriptions and cursor-based replay.

Catalog and notebook streams filter a shared log. Clients resume each
stream from the last event id received on that stream.
"""

from __future__ import annotations

import logging
import secrets
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable, Collection, Iterator
from contextlib import AbstractContextManager, contextmanager
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone

import msgspec
from msgspec import UNSET

from marimo._core import protocol, protocol_events

LOGGER = logging.getLogger(__name__)


def snapshot_event(
    body: protocol_events.SnapshotBody,
    *,
    notebook_id: protocol.NotebookId | None = None,
    run_id: protocol.RunId | None = None,
    request_id: str | None = None,
) -> RoutedEvent:
    """Copy current state into an event without an emission time or cursor."""
    return RoutedEvent(
        protocol_events.record(
            deepcopy(body),
            request_id=UNSET if request_id is None else request_id,
        ),
        notebook_id=notebook_id,
        run_id=run_id,
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def removal(
    record_type: type[protocol_events.RemovableBody],
    object_id: str,
    *,
    notebook_id: protocol.NotebookId | None = None,
    request_id: str | None = None,
    run_id: protocol.RunId | None = None,
) -> RoutedEvent:
    """Return an event announcing an object's removal."""
    return RoutedEvent(
        protocol_events.removed(
            record_type,
            object_id,
            request_id=UNSET if request_id is None else request_id,
            time=utcnow(),
        ),
        notebook_id=notebook_id,
        run_id=run_id,
    )


class ExtensionEvent(msgspec.Struct, frozen=True, tag_field="event"):
    """Base envelope for host extensions outside the public protocol.

    Subclasses declare their event tag and payload type.
    """

    data: msgspec.Struct
    id: str | msgspec.UnsetType = UNSET


def event_name(event: protocol.Event | ExtensionEvent) -> str:
    """Read the wire tag for transport framing and client type filters."""
    tag = event.__struct_config__.tag
    assert isinstance(tag, str)
    return tag


@dataclass(frozen=True)
class RoutedEvent:
    """A typed wire event with internal notebook and run routing."""

    event: protocol.Event | ExtensionEvent
    notebook_id: protocol.NotebookId | None = None
    run_id: protocol.RunId | None = None

    @property
    def position(self) -> int | None:
        """The event's position in its stream, absent on snapshots and resets."""
        if self.event.id is UNSET:
            return None
        return int(self.event.id.rpartition("-")[2])

    def visible_in(self, notebook_id: str | None) -> bool:
        """Whether the event belongs in the catalog or notebook stream."""
        if isinstance(self.event, (protocol.ReadyEvent, protocol.ResetEvent)):
            return False
        if notebook_id is None:
            return isinstance(
                self.event,
                (
                    protocol.HostEvent,
                    protocol.ProjectEvent,
                    protocol.ProjectRemovedEvent,
                    protocol.NotebookEvent,
                    protocol.NotebookRemovedEvent,
                    protocol.RuntimeEvent,
                    protocol.RuntimeRemovedEvent,
                    protocol.AttachmentEvent,
                    protocol.AttachmentRemovedEvent,
                ),
            )
        return self.notebook_id == notebook_id and not isinstance(
            self.event,
            (
                protocol.HostEvent,
                protocol.ProjectEvent,
                protocol.ProjectRemovedEvent,
            ),
        )

    def wanted(
        self, types: Collection[str] | None, run_id: str | None = None
    ) -> bool:
        """Apply kind and run filters, always including `ready` and `reset`."""
        if isinstance(self.event, (protocol.ReadyEvent, protocol.ResetEvent)):
            return True
        if types is not None:
            kind = event_name(self.event)
            if isinstance(self.event, protocol_events.RemovalEvent):
                kind = kind.removesuffix(".removed")
            if kind not in types:
                return False
        return run_id is None or self.run_id == run_id


Listener = Callable[[RoutedEvent], None]


class Sink(ABC):
    """Where a producer publishes its events.

    A `Stream` is a sink. A host can give a notebook one that observes
    each event before the stream records it.
    """

    def append(self, event: RoutedEvent) -> RoutedEvent:
        """Record an event without requiring a public protocol type."""
        return self._append(deepcopy(event))

    def publish(
        self,
        body: protocol_events.Body,
        *,
        notebook_id: protocol.NotebookId | None = None,
        request_id: str | None = None,
        run_id: protocol.RunId | None = None,
    ) -> RoutedEvent:
        """Publish a new or updated object."""
        return self._append(
            RoutedEvent(
                protocol_events.record(
                    deepcopy(body),
                    request_id=UNSET if request_id is None else request_id,
                    time=utcnow(),
                ),
                notebook_id=notebook_id,
                run_id=run_id,
            )
        )

    def remove(
        self,
        record_type: type[protocol_events.RemovableBody],
        object_id: str,
        *,
        notebook_id: protocol.NotebookId | None = None,
        request_id: str | None = None,
        run_id: protocol.RunId | None = None,
    ) -> RoutedEvent:
        """Publish an object's removal."""
        return self._append(
            removal(
                record_type,
                object_id,
                notebook_id=notebook_id,
                request_id=request_id,
                run_id=run_id,
            )
        )

    @abstractmethod
    def deferred(self) -> AbstractContextManager[None]:
        """Deliver events published in the block once it ends."""

    @abstractmethod
    def _append(self, event: RoutedEvent) -> RoutedEvent:
        """Record an owned event and return an isolated copy as recorded.

        The event must already be isolated from the caller. Forward it to
        another sink's `_append` without copying it again.
        """


class Stream(Sink):
    """An ordered event log with bounded history and live subscriptions.

    Callers serialize access on one thread. Published objects and returned
    events are copied so readers cannot mutate the log or each other's data.
    """

    def __init__(self, *, history: int = 1000) -> None:
        # Cursors name the stream that issued them, so a cursor from before
        # a restart resets instead of replaying another history.
        self._epoch = secrets.token_hex(4)
        self._last_id = 0
        self._history: deque[RoutedEvent] = deque(maxlen=history)
        self._listeners: list[Listener] = []
        self._pending: deque[tuple[RoutedEvent, tuple[Listener, ...]]] = (
            deque()
        )
        self._dispatching = False

    @property
    def last_id(self) -> int:
        return self._last_id

    @property
    def cursor(self) -> str:
        """The cursor of the last event, as `ready` carries it."""
        return self.cursor_at(self._last_id)

    def cursor_at(self, position: int) -> str:
        """Return the cursor this stream issues for `position`."""
        return f"{self._epoch}-{position}"

    def position(self, cursor: str) -> int | None:
        """Return the position `cursor` names, or `None` if another stream issued it."""
        epoch, _, position = cursor.partition("-")
        # Header text is latin-1, where superscripts count as digits.
        if epoch != self._epoch or not (
            position.isascii() and position.isdigit()
        ):
            return None
        return int(position)

    def since(self, position: int) -> list[RoutedEvent] | None:
        """Return events after `position`, or `None` for a stale or future one."""
        if position == self._last_id:
            return []
        if position > self._last_id:
            return None
        oldest = (
            self._history[0].position if self._history else self._last_id + 1
        )
        assert oldest is not None
        if position < oldest - 1:
            return None
        return deepcopy(
            [
                e
                for e in self._history
                if e.position is not None and e.position > position
            ]
        )

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Subscribe to future events and return an unsubscribe function.

        Subscriber exceptions are logged. Events published during delivery
        follow the event being delivered.
        """
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    @contextmanager
    def deferred(self) -> Iterator[None]:
        """Deliver events published in the block once it ends.

        Events still join the history at once, so cursors and replay are
        unaffected. Nested blocks defer to the outermost one.
        """
        if self._dispatching:
            yield
            return
        self._dispatching = True
        try:
            yield
        finally:
            self._dispatching = False
            self._drain()

    def _append(self, event: RoutedEvent) -> RoutedEvent:
        self._last_id += 1
        stamped = replace(
            event,
            event=msgspec.structs.replace(event.event, id=self.cursor),
        )
        self._history.append(stamped)
        self._pending.append((stamped, tuple(self._listeners)))
        if not self._dispatching:
            self._drain()
        return deepcopy(stamped)

    def _drain(self) -> None:
        self._dispatching = True
        try:
            while self._pending:
                pending, listeners = self._pending.popleft()
                for listener in listeners:
                    try:
                        listener(deepcopy(pending))
                    except Exception:
                        LOGGER.exception("Error delivering host event")
        finally:
            self._dispatching = False
