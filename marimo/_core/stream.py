# Copyright 2026 Marimo. All rights reserved.
"""Ordered events with subscriptions and cursor-based replay.

Catalog and notebook streams filter a shared log. Clients resume each
stream from the last event id received on that stream.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable, Collection, Iterator
from contextlib import AbstractContextManager, contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, TypeAlias, get_args

import msgspec
from msgspec import UNSET

from marimo._core import protocol

LOGGER = logging.getLogger(__name__)

Body: TypeAlias = (
    protocol.Host
    | protocol.Project
    | protocol.Notebook
    | protocol.Document
    | protocol.Analysis
    | protocol.Cell
    | protocol.Runtime
    | protocol.Attachment
    | protocol.Run
    | protocol.Execution
    | protocol.Console
    | protocol.Display
    | protocol.Custom
)
"""Every object a stream carries. The wrapper map and the notebook kinds
derive from it; the catalog kinds are a chosen subset."""


Kind: TypeAlias = Literal[
    "host",
    "project",
    "notebook",
    "document",
    "analysis",
    "cell",
    "runtime",
    "attachment",
    "run",
    "execution",
    "console",
    "display",
    "custom",
]
"""The kinds of object a stream carries, one per `Body` type."""

_KIND_BY_NAME: dict[str, Kind] = {kind: kind for kind in get_args(Kind)}
assert set(_KIND_BY_NAME) == {
    body_type.__name__.lower() for body_type in get_args(Body)
}


def kind_of(body: Body) -> Kind:
    """Return the object's event kind, used by the `types` filter."""
    return _KIND_BY_NAME[type(body).__name__.lower()]


_WRAPPERS: dict[Kind, type[msgspec.Struct]] = {
    _KIND_BY_NAME[body_type.__name__.lower()]: getattr(
        protocol, f"{body_type.__name__}Message"
    )
    for body_type in get_args(Body)
}

CATALOG_KINDS: frozenset[Kind] = frozenset(
    {"host", "project", "notebook", "runtime", "attachment"}
)
# Host and project describe the whole host, so they never belong to one
# notebook's stream. Every other kind does.
NOTEBOOK_KINDS = frozenset(_WRAPPERS) - {"host", "project"}


def message(
    body: Body,
    *,
    request_id: str | None = None,
    time: datetime | None = None,
) -> msgspec.Struct:
    """Wrap an object in its protocol message."""
    kind = kind_of(body)
    fields: dict[str, Body] = {kind: deepcopy(body)}
    return _WRAPPERS[kind](
        **fields,
        request_id=UNSET if request_id is None else request_id,
        time=UNSET if time is None else time,
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def removal(
    kind: Kind,
    object_id: str,
    *,
    notebook_id: protocol.NotebookId | None = None,
    request_id: str | None = None,
    run_id: protocol.RunId | None = None,
) -> Event:
    """Return an event announcing an object's removal."""
    data = protocol.RemovedMessage(
        id=object_id,
        request_id=UNSET if request_id is None else request_id,
        time=utcnow(),
    )
    return Event(
        f"{kind}.removed", data, notebook_id=notebook_id, run_id=run_id
    )


@dataclass(frozen=True)
class Event:
    """An event with an optional replay cursor and notebook scope.

    Snapshot events have no `id`. Control events have no `data`.
    """

    name: str
    data: msgspec.Struct | None = None
    id: int | None = None
    notebook_id: protocol.NotebookId | None = None
    run_id: protocol.RunId | None = None

    @property
    def kind(self) -> Kind | None:
        """The object kind without the `.removed` suffix.

        `ready` and `reset` carry no object and have no kind.
        """
        return _KIND_BY_NAME.get(self.name.partition(".")[0])

    def visible_in(self, notebook_id: str | None) -> bool:
        """Whether the event belongs in the catalog or notebook stream."""
        if notebook_id is None:
            return self.kind in CATALOG_KINDS
        return self.notebook_id == notebook_id and self.kind in NOTEBOOK_KINDS

    def wanted(
        self, types: Collection[str] | None, run_id: str | None = None
    ) -> bool:
        """Apply kind and run filters, always including `ready` and `reset`."""
        if self.name in ("ready", "reset"):
            return True
        return (types is None or self.kind in types) and (
            run_id is None or self.run_id == run_id
        )


Listener = Callable[[Event], None]


class Sink(ABC):
    """Where a producer publishes its events.

    A `Stream` is a sink. A host can give a notebook one that observes
    each event before the stream records it.
    """

    def publish(
        self,
        body: Body,
        *,
        notebook_id: protocol.NotebookId | None = None,
        request_id: str | None = None,
        run_id: protocol.RunId | None = None,
    ) -> Event:
        """Publish a new or updated object."""
        data = message(body, request_id=request_id, time=utcnow())
        return self._append(
            Event(kind_of(body), data, notebook_id=notebook_id, run_id=run_id)
        )

    def remove(
        self,
        kind: Kind,
        object_id: str,
        *,
        notebook_id: protocol.NotebookId | None = None,
        request_id: str | None = None,
        run_id: protocol.RunId | None = None,
    ) -> Event:
        """Publish an object's removal."""
        return self._append(
            removal(
                kind,
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
    def _append(self, event: Event) -> Event:
        """Record an event and return it as recorded."""


class Stream(Sink):
    """An ordered event log with bounded history and live subscriptions.

    Callers serialize access on one thread. Published objects and returned
    events are copied so readers cannot mutate the log or each other's data.
    """

    def __init__(self, *, history: int = 1000) -> None:
        self._last_id = 0
        self._history: deque[Event] = deque(maxlen=history)
        self._listeners: list[Listener] = []
        self._pending: deque[tuple[Event, tuple[Listener, ...]]] = deque()
        self._dispatching = False

    @property
    def last_id(self) -> int:
        return self._last_id

    def since(self, cursor: int) -> list[Event] | None:
        """Return events after `cursor`, or `None` for a stale or future cursor."""
        if cursor == self._last_id:
            return []
        if cursor > self._last_id:
            return None
        oldest = self._history[0].id if self._history else self._last_id + 1
        assert oldest is not None
        if cursor < oldest - 1:
            return None
        return deepcopy(
            [e for e in self._history if e.id is not None and e.id > cursor]
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

    def append(self, event: Event) -> Event:
        """Record an emitted event with a cursor belonging to this log."""
        return self._append(deepcopy(event))

    def _append(self, event: Event) -> Event:
        self._last_id += 1
        stamped = Event(
            event.name,
            event.data,
            self._last_id,
            event.notebook_id,
            event.run_id,
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
