# Copyright 2026 Marimo. All rights reserved.
"""Dataflow API session management on top of marimo's ``SessionManager``.

A ``DataflowFileBundle`` is a thin facade over a real :class:`Session` for a
notebook file. It owns a phantom :class:`DataflowAnchorConsumer` so the
session can exist without an editor websocket attached, and routes dataflow
HTTP requests through the kernel's :class:`DataflowCallbacks` via the
``ScopedRunCommand`` family of control messages.

When an editor websocket attaches to the same file, marimo's existing
multi-consumer plumbing (the same code path that powers kiosk and RTC) lets
both consumers share the kernel: the editor sees cell outputs, dataflow
clients see typed variable values, and either side can drive UI elements.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from marimo import _loggers as loggers
from marimo._dataflow.consumer import (
    DataflowAnchorConsumer,
    DataflowSseConsumer,
)
from marimo._dataflow.protocol import DataflowEvent, DataflowSchema, RunEvent
from marimo._messaging.notification import DataflowSchemaNotification
from marimo._runtime.commands import (
    GetDataflowSchemaCommand,
    HTTPRequest,
    RemoveDataflowSubscriptionsCommand,
    ScopedRunCommand,
)
from marimo._types.ids import ConsumerId, SessionId, UIElementId

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from marimo._messaging.types import KernelMessage
    from marimo._server.session_manager import SessionManager
    from marimo._session.types import Session


LOGGER = loggers.marimo_logger()


class DataflowFileBundle:
    """Per-file dataflow state: a live ``Session`` plus a name→object_id map.

    The bundle lazily creates a session on first use via
    ``SessionManager.create_session`` with a phantom anchor consumer so the
    session has the required main consumer. The schema is sourced from the
    kernel via ``DataflowSchemaNotification`` and cached here keyed by
    ``schema_id``; the kernel re-emits whenever the file changes.
    """

    def __init__(
        self,
        *,
        session_manager: SessionManager,
        file_key: str,
    ) -> None:
        self._session_manager = session_manager
        self._file_key = file_key
        self._session: Session | None = None
        self._anchor: DataflowAnchorConsumer | None = None
        self._schema: DataflowSchema | None = None
        self._schema_id: str | None = None
        self._schema_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._input_object_ids: dict[str, UIElementId] = {}

    @property
    def session(self) -> Session | None:
        return self._session

    async def ensure_session(self) -> Session:
        """Look up the session for this file or create one with an anchor.

        Newly created sessions are kicked off with an explicit instantiate
        request so cells run, ``mo.api.input`` UI elements get registered,
        and the schema can be computed. Reused sessions are assumed to
        already have been instantiated by whoever opened them first.
        """
        async with self._lock:
            if self._session is not None and not self._session_closed():
                return self._session

            existing = self._session_manager.get_session_by_file_key(
                self._file_key  # type: ignore[arg-type]
            )
            if existing is not None:
                self._attach_to_session(existing)
                return existing

            anchor = DataflowAnchorConsumer(
                consumer_id=f"dataflow-anchor-{uuid4().hex[:8]}"
            )
            session_id = SessionId(f"dataflow-{uuid4().hex[:8]}")
            session = self._session_manager.create_session(
                session_id=session_id,
                session_consumer=anchor,
                query_params={},
                file_key=self._file_key,  # type: ignore[arg-type]
                auto_instantiate=True,
            )
            self._anchor = anchor
            self._attach_to_session(session)
            session.instantiate(
                _empty_instantiate_request(), http_request=None
            )
            return session

    def _session_closed(self) -> bool:
        return getattr(self._session, "_closed", False)

    def _attach_to_session(self, session: Session) -> None:
        """Install our schema-tracking listener on the given session."""
        if self._session is session:
            return
        self._session = session
        listener = _SchemaListener(self)
        # Attach as a non-main consumer; main is the anchor (or the editor).
        session.connect_consumer(listener, main=False)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def get_schema(self, *, timeout: float = 30.0) -> DataflowSchema:
        """Return the latest schema, requesting a fresh broadcast if needed."""
        session = await self.ensure_session()
        if self._schema is not None:
            return self._schema

        # Trigger a fresh broadcast in case auto-instantiate happened before
        # we attached our schema listener.
        session.put_control_request(
            GetDataflowSchemaCommand(),
            from_consumer_id=ConsumerId(self._anchor.consumer_id)
            if self._anchor
            else None,
        )
        try:
            await asyncio.wait_for(self._schema_event.wait(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise RuntimeError(
                f"Timed out after {timeout}s waiting for dataflow schema"
            ) from exc
        assert self._schema is not None
        return self._schema

    def _on_schema_received(
        self,
        schema: DataflowSchema,
        input_object_ids: dict[str, str],
    ) -> None:
        self._schema = schema
        self._schema_id = schema.schema_id
        self._input_object_ids = {
            name: UIElementId(oid) for name, oid in input_object_ids.items()
        }
        self._schema_event.set()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    async def run(
        self,
        *,
        inputs: dict[str, Any],
        subscribed: set[str],
        consumer_id: str,
        run_id: str,
        request: HTTPRequest | None = None,
        timeout: float = 60.0,
    ) -> AsyncIterator[DataflowEvent]:
        """Drive a single run and stream events.

        Returns an async generator over ``DataflowEvent``s. The generator
        completes when the run's ``done`` event arrives or the timeout
        elapses.
        """
        session = await self.ensure_session()
        await self.get_schema(timeout=timeout)

        consumer = DataflowSseConsumer(
            consumer_id=consumer_id,
            subscribed=subscribed,
            run_id=run_id,
        )
        session.connect_consumer(consumer, main=False)

        scoped = ScopedRunCommand(
            consumer_id=consumer_id,
            run_id=run_id,
            inputs=self._resolve_inputs(inputs),
            subscribed=sorted(subscribed),
            request=request,
        )
        session.put_control_request(
            scoped, from_consumer_id=ConsumerId(consumer_id)
        )

        started_at = time.time()
        yield RunEvent(run_id=run_id, status="started", elapsed_ms=None)

        try:
            while True:
                event = await consumer.get_event(timeout=timeout)
                if event is None:
                    break
                # The consumer emits a done RunEvent on receiving
                # CompletedRunNotification — use it as our loop terminator
                # but suppress on the wire; the canonical done event with
                # elapsed_ms is yielded below.
                if isinstance(event, RunEvent) and event.status == "done":
                    break
                yield event
        finally:
            session.disconnect_consumer(consumer)
            session.put_control_request(
                RemoveDataflowSubscriptionsCommand(consumer_id=consumer_id),
                from_consumer_id=ConsumerId(consumer_id),
            )
            yield RunEvent(
                run_id=run_id,
                status="done",
                elapsed_ms=(time.time() - started_at) * 1000,
            )

    def _resolve_inputs(
        self, inputs: dict[str, Any]
    ) -> dict[UIElementId, Any]:
        """Map input names → UI element ids using the session view."""
        if not inputs:
            return {}
        if self._session is None:
            return {}

        # The ``mo.api.input`` UIElements live in the kernel's globals;
        # their ``_id`` is the ``object_id`` we need. The ``SessionView``
        # tracks known UI element values by id, but doesn't expose the
        # bound name. We rely on a periodic ``variables`` op or a future
        # explicit kernel rpc; for now consult the cached map.
        return {
            UIElementId(self._input_object_ids[name]): value
            for name, value in inputs.items()
            if name in self._input_object_ids
        }


class _SchemaListener:
    """Lightweight session consumer that forwards schemas to the bundle."""

    def __init__(self, bundle: DataflowFileBundle) -> None:
        self._bundle = bundle
        self._id = ConsumerId(f"dataflow-schema-listener-{uuid4().hex[:6]}")

    @property
    def consumer_id(self) -> ConsumerId:
        return self._id

    def notify(self, notification: KernelMessage) -> None:
        from marimo._messaging.serde import deserialize_kernel_message

        try:
            decoded = deserialize_kernel_message(notification)
        except Exception:
            return
        if not isinstance(decoded, DataflowSchemaNotification):
            return
        try:
            schema = _decode_schema(decoded)
        except Exception:
            LOGGER.exception("Failed to decode dataflow schema")
            return
        self._bundle._on_schema_received(schema, decoded.input_object_ids)

    def connection_state(self) -> Any:
        from marimo._session.model import ConnectionState

        return ConnectionState.OPEN

    def on_attach(self, session: Any, event_bus: Any) -> None:
        del session, event_bus

    def on_detach(self) -> None:
        pass


def _decode_schema(notification: DataflowSchemaNotification) -> DataflowSchema:
    import msgspec

    encoded = msgspec.json.encode(notification.schema)
    schema = msgspec.json.decode(encoded, type=DataflowSchema)
    if not schema.schema_id:
        schema = DataflowSchema(
            inputs=schema.inputs,
            outputs=schema.outputs,
            triggers=schema.triggers,
            schema_id=notification.schema_id,
        )
    return schema


class DataflowSessionManager:
    """Registry of ``DataflowFileBundle``s keyed on file path.

    Holds a back-reference to marimo's :class:`SessionManager` so we can
    look up or create real ``Session``s on demand. There is exactly one
    ``DataflowSessionManager`` per server process.
    """

    def __init__(self, session_manager: SessionManager) -> None:
        self._session_manager = session_manager
        self._bundles: dict[str, DataflowFileBundle] = {}

    @property
    def session_manager(self) -> SessionManager:
        return self._session_manager

    def get_bundle(self, file_key: str) -> DataflowFileBundle:
        bundle = self._bundles.get(file_key)
        if bundle is None:
            bundle = DataflowFileBundle(
                session_manager=self._session_manager,
                file_key=file_key,
            )
            self._bundles[file_key] = bundle
        return bundle


def _empty_instantiate_request() -> Any:
    """Build a minimal ``InstantiateNotebookRequest`` with no UI overrides."""
    from marimo._server.models.models import InstantiateNotebookRequest

    return InstantiateNotebookRequest(object_ids=[], values=[])


__all__ = [
    "DataflowFileBundle",
    "DataflowSessionManager",
]
