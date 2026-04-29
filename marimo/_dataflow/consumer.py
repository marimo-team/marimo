# Copyright 2026 Marimo. All rights reserved.
"""Session consumers for the dataflow API.

The kernel publishes ``dataflow-schema`` and ``dataflow-var`` notifications
through the regular ``Room`` broadcast path. Two consumer types live on the
host side:

- :class:`DataflowAnchorConsumer` — a phantom main consumer that keeps a
  ``Session`` alive between dataflow requests and satisfies the
  "exactly one main consumer" invariant when no editor is attached.
- :class:`DataflowSseConsumer` — a transient consumer attached for the
  duration of one SSE response. Filters kernel notifications by
  ``consumer_id`` and projects them into the ``DataflowEvent`` wire union
  drained by the HTTP handler.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import msgspec

from marimo._dataflow.protocol import (
    DataflowEvent,
    DataflowSchema,
    InputSchema,
    Kind,
    OutputSchema,
    RunEvent,
    SchemaEvent,
    TriggerSchema,
    VarErrorEvent,
    VarEvent,
)
from marimo._messaging.notification import (
    CompletedRunNotification,
    DataflowSchemaNotification,
    DataflowVarErrorNotification,
    DataflowVarNotification,
)
from marimo._messaging.serde import deserialize_kernel_message
from marimo._session.consumer import SessionConsumer
from marimo._session.model import ConnectionState
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from marimo._messaging.types import KernelMessage
    from marimo._session.events import SessionEventBus
    from marimo._session.types import Session


class DataflowAnchorConsumer(SessionConsumer):
    """Always-on consumer that keeps a dataflow-created session alive.

    Marimo's :class:`Session` requires exactly one *main* consumer. When the
    dataflow API creates a session before any editor websocket has attached
    we install one of these as the main consumer. It silently drops every
    notification it receives — broadcasts to dataflow SSE clients happen on
    *non-main* consumers attached per request.
    """

    def __init__(self, consumer_id: str = "dataflow-anchor") -> None:
        self._id = ConsumerId(consumer_id)

    @property
    def consumer_id(self) -> ConsumerId:
        return self._id

    def notify(self, notification: KernelMessage) -> None:  # noqa: D401
        del notification

    def connection_state(self) -> ConnectionState:
        return ConnectionState.OPEN

    def on_attach(
        self, session: Session, event_bus: SessionEventBus
    ) -> None:
        del session, event_bus

    def on_detach(self) -> None:
        pass


class DataflowSseConsumer(SessionConsumer):
    """Per-request session consumer that drives one SSE response.

    Filters kernel notifications by ``consumer_id`` and projects the
    relevant ones into ``DataflowEvent``s on an internal queue. The HTTP
    handler awaits :meth:`get_event` to drain.
    """

    def __init__(
        self,
        *,
        consumer_id: str,
        subscribed: set[str],
        run_id: str,
    ) -> None:
        self._id = ConsumerId(consumer_id)
        self._subscribed = set(subscribed)
        self._run_id = run_id
        self._queue: asyncio.Queue[DataflowEvent | None] = asyncio.Queue()
        self._closed = False
        # Cached schema events arrive as ``dataflow-schema`` ops; we track
        # the latest schema id so we can de-dupe when one client gets the
        # same schema rebroadcast across runs.
        self._last_schema_id: str | None = None

    @property
    def consumer_id(self) -> ConsumerId:
        return self._id

    @property
    def subscribed(self) -> set[str]:
        return self._subscribed

    def notify(self, notification: KernelMessage) -> None:
        if self._closed:
            return
        try:
            decoded = deserialize_kernel_message(notification)
        except Exception:
            return
        if isinstance(decoded, DataflowSchemaNotification):
            self._handle_schema(decoded)
        elif isinstance(decoded, DataflowVarNotification):
            self._handle_var(decoded)
        elif isinstance(decoded, DataflowVarErrorNotification):
            self._handle_var_error(decoded)
        elif isinstance(decoded, CompletedRunNotification):
            self._handle_completed()

    def connection_state(self) -> ConnectionState:
        return ConnectionState.CLOSED if self._closed else ConnectionState.OPEN

    def on_attach(
        self, session: Session, event_bus: SessionEventBus
    ) -> None:
        del session, event_bus

    def on_detach(self) -> None:
        self._closed = True
        self._queue.put_nowait(None)

    async def get_event(
        self, timeout: float | None = None
    ) -> DataflowEvent | None:
        """Pop the next event, or ``None`` if the consumer was detached."""
        try:
            if timeout is None:
                return await self._queue.get()
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    # ------------------------------------------------------------------
    # Op-specific projections
    # ------------------------------------------------------------------

    def _handle_schema(self, decoded: DataflowSchemaNotification) -> None:
        if decoded.schema_id and decoded.schema_id == self._last_schema_id:
            return
        try:
            schema = _decode_schema(decoded.schema, decoded.schema_id)
        except Exception:
            return
        self._last_schema_id = decoded.schema_id
        self._queue.put_nowait(
            SchemaEvent(schema=schema, schema_id=decoded.schema_id)
        )

    def _handle_var(self, decoded: DataflowVarNotification) -> None:
        if decoded.consumer_id != str(self._id):
            return
        if decoded.var_name not in self._subscribed:
            return
        try:
            kind = Kind(decoded.kind)
        except ValueError:
            kind = Kind.ANY
        self._queue.put_nowait(
            VarEvent(
                name=decoded.var_name,
                kind=kind,
                encoding=decoded.encoding,
                run_id=decoded.run_id,
                seq=decoded.seq,
                value=decoded.value,
                ref=decoded.ref,
            )
        )

    def _handle_var_error(
        self, decoded: DataflowVarErrorNotification
    ) -> None:
        if decoded.consumer_id != str(self._id):
            return
        if decoded.var_name not in self._subscribed:
            return
        self._queue.put_nowait(
            VarErrorEvent(
                name=decoded.var_name,
                run_id=decoded.run_id,
                error=decoded.error,
                traceback=decoded.traceback,
            )
        )

    def _handle_completed(self) -> None:
        # Every kernel command emits a CompletedRunNotification at the end
        # (including subscription/schema commands that don't run cells).
        # We translate it into a ``done`` RunEvent so the HTTP handler
        # knows to stop draining.
        self._queue.put_nowait(
            RunEvent(
                run_id=self._run_id,
                status="done",
                elapsed_ms=None,
            )
        )


def _decode_schema(raw: dict[str, Any], schema_id: str) -> DataflowSchema:
    """Round-trip a schema dict (camelCase, from msgspec) into the struct."""
    encoded = msgspec.json.encode(raw)
    schema = msgspec.json.decode(encoded, type=DataflowSchema)
    if not schema.schema_id:
        # Some encoders drop empty schema_id; reuse the wrapping id.
        schema = DataflowSchema(
            inputs=schema.inputs,
            outputs=schema.outputs,
            triggers=schema.triggers,
            schema_id=schema_id,
        )
    return schema


def make_run_started_event(run_id: str) -> RunEvent:
    """Build the ``run`` event the HTTP handler emits before relaying."""
    return RunEvent(run_id=run_id, status="started", elapsed_ms=None)


def make_run_done_event(run_id: str, started_at: float) -> RunEvent:
    """Build the closing ``run`` event with elapsed time."""
    return RunEvent(
        run_id=run_id,
        status="done",
        elapsed_ms=(time.time() - started_at) * 1000,
    )


__all__ = [
    "DataflowAnchorConsumer",
    "DataflowSseConsumer",
    "InputSchema",
    "OutputSchema",
    "TriggerSchema",
    "make_run_done_event",
    "make_run_started_event",
]
