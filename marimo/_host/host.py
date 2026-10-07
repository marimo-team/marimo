# Copyright 2026 Marimo. All rights reserved.
"""The owner of a host's state over time.

A host holds one current state, applies changes to it, and publishes
the resulting events, handing kernel work to a runtime. Changes are
applied one at a time, on the event loop.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol

import msgspec

from marimo import _loggers
from marimo._host import protocol
from marimo._host.model import Failed, Running
from marimo._host.stream import Event, diff, snapshot
from marimo._host.transitions import (
    Action,
    Command,
    Observation,
    RestartRuntime,
    StartRuntime,
    StopRuntime,
    apply,
)

if TYPE_CHECKING:
    from marimo._host.model import HostState
    from marimo._types.ids import NotebookId, RuntimeId


LOGGER = _loggers.marimo_logger()


class KernelRuntime(Protocol):
    """What a host needs from whatever runs kernels."""

    def perform(self, action: Action) -> None:
        """Starts or stops a kernel as the action says, without waiting.

        The runtime reports what came of it through `Host.observe`, naming
        the action's generation.
        """


Listener = Callable[[Event], None]
"""Receives each published event, in order, with its id and time set."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Host:
    """Applies changes to a host's state and publishes the events.

    Events are numbered, and the most recent ones are kept so a client
    can resume from a cursor. One too old to resume gets a reset.
    """

    def __init__(
        self,
        state: HostState,
        runtime: KernelRuntime,
        *,
        operations: Sequence[str],
        history: int = 1000,
    ) -> None:
        self._state = state
        self._runtime = runtime
        self._host = protocol.Host(operations=list(operations))
        self._last_id = 0
        self._history: deque[Event] = deque(maxlen=history)
        self._listeners: list[Listener] = []
        # A request's id follows the runtime it changed until that runtime
        # settles, so a client sees its request through to the end.
        self._pending: dict[RuntimeId, str] = {}

    @property
    def state(self) -> HostState:
        """The current state."""
        return self._state

    @property
    def operations(self) -> list[str]:
        return list(self._host.operations)

    def command(
        self, command: Command, *, request_id: str | None = None
    ) -> HostState:
        """Applies a client's command and returns the new state.

        Events caused by it carry `request_id`, and so do later events about
        a runtime it started, restarted, or stopped, until that settles.

        Raises:
            NotFound: If the command names something the host does not have.
            NoRuntime: If the command needs a runtime the notebook lacks.
            Conflict: If the command does not fit the notebook's state.
        """
        self._apply(command, request_id)
        return self._state

    def observe(
        self, observation: Observation, *, request_id: str | None = None
    ) -> None:
        """Applies something a runtime or connection reports.

        A stale report changes nothing and raises nothing.
        """
        self._apply(observation, request_id)

    def events(
        self,
        cursor: int | None = None,
        *,
        notebook_id: NotebookId | None = None,
    ) -> list[Event]:
        """Returns the events a connection should receive first.

        Without a cursor, a snapshot. With one the history still covers, the
        events since it; otherwise `reset` and a snapshot. `ready` ends the
        list and carries the cursor to keep.
        """
        ready = Event("ready", id=self._last_id)
        if cursor is None:
            return [*self._snapshot(notebook_id), ready]
        missed = self._since(cursor)
        if missed is None:
            return [Event("reset"), *self._snapshot(notebook_id), ready]
        return [*_about(missed, notebook_id), ready]

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Sends every event published from now on to `listener`.

        Returns a function that unsubscribes. Call `events` first and skip
        anything with an id at or below the `ready` cursor.
        """
        self._listeners.append(listener)

        def unsubscribe() -> None:
            self._listeners.remove(listener)

        return unsubscribe

    def _snapshot(self, notebook_id: NotebookId | None) -> list[Event]:
        events = snapshot(self._host, self._state, at=_utcnow())
        if notebook_id is None:
            return events
        return _about(events, notebook_id)

    def _apply(
        self, change: Command | Observation, request_id: str | None
    ) -> None:
        outcome = apply(self._state, change)
        if outcome.state is self._state:
            return
        time = _utcnow()
        events = diff(self._state, outcome.state, at=time)
        self._state = outcome.state

        if request_id is not None:
            runtime_id = self._runtime_changed_by(change)
            if runtime_id is not None:
                self._pending[runtime_id] = request_id

        for event in events:
            self._publish(event, time, request_id)
        # A request is done once its runtime settles. Checked after all of
        # this change's events, since a runtime that ends produces several.
        self._pending = {
            runtime_id: pending
            for runtime_id, pending in self._pending.items()
            if not self._settled(runtime_id)
        }

        # Actions run after the events are out, so a runtime that reports
        # back at once observes the state these events describe.
        for action in outcome.actions:
            self._runtime.perform(action)

    def _publish(
        self, event: Event, time: datetime, caused_by: str | None
    ) -> None:
        self._last_id += 1
        runtime_id = event.runtime_id()
        request_id: str | msgspec.UnsetType = msgspec.UNSET
        if caused_by is not None:
            request_id = caused_by
        elif runtime_id is not None:
            request_id = self._pending.get(runtime_id, msgspec.UNSET)
        assert event.data is not None
        stamped = Event(
            event.name,
            msgspec.structs.replace(
                event.data, request_id=request_id, time=time
            ),
            id=self._last_id,
            notebook_id=event.notebook_id,
        )
        self._history.append(stamped)
        for listener in list(self._listeners):
            # A listener is a bystander. One that fails must not keep the
            # others from hearing, or the runtime from acting.
            try:
                listener(stamped)
            except Exception:
                LOGGER.exception("A host listener failed on %s", event.name)

    def _since(self, cursor: int) -> list[Event] | None:
        """Returns the events after `cursor`, or `None` if any were lost."""
        if cursor == self._last_id:
            return []
        if not self._history or cursor < self._history[0].id - 1:  # type: ignore[operator]
            return None
        return [e for e in self._history if e.id > cursor]  # type: ignore[operator]

    def _runtime_changed_by(
        self, change: Command | Observation
    ) -> RuntimeId | None:
        if isinstance(change, (StartRuntime, RestartRuntime, StopRuntime)):
            notebook = self._state.notebooks.get(change.notebook_id)
            runtime = None if notebook is None else notebook.runtime
            if runtime is not None:
                return runtime.id
            # Stopped and gone at once; nothing left to follow.
            return None
        # Executions carry their own key on every report.
        return None

    def _settled(self, runtime_id: RuntimeId) -> bool:
        located = self._state.locate(runtime_id)
        if located is None:
            return True
        return isinstance(located[1].lifecycle, (Running, Failed))


def _about(events: list[Event], notebook_id: NotebookId | None) -> list[Event]:
    """Keeps the events about `notebook_id`, or all of them if it is `None`."""
    if notebook_id is None:
        return events
    return [e for e in events if e.notebook_id == notebook_id]
