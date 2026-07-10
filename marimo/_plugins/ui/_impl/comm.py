# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from marimo._loggers import marimo_logger
from marimo._messaging.notification import (
    EsmSpec,
    ModelClose,
    ModelCustom,
    ModelLifecycleNotification,
    ModelMessage,
    ModelOpen,
    ModelUpdate,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._plugins.ui._impl.anywidget.widget_ref import (
    AnyWidgetStateSerializer,
)
from marimo._runtime.commands import (
    ModelCommand,
    ModelUpdateMessage,
)
from marimo._types.ids import WidgetModelId

if TYPE_CHECKING:
    from marimo._messaging.types import Stream
    from marimo._runtime.context.utils import RunMode

LOGGER = marimo_logger()


@dataclass
class MarimoCommManager:
    comms: dict[WidgetModelId, MarimoComm] = field(default_factory=dict)

    def register_comm(self, comm: MarimoComm) -> str:
        comm_id = comm.comm_id
        self.comms[comm_id] = comm
        return comm_id

    def unregister_comm(self, comm: MarimoComm) -> MarimoComm:
        return self.comms.pop(comm.comm_id)

    def receive_comm_message(
        self,
        command: ModelCommand,
    ) -> tuple[str | None, dict[str, Any] | None]:
        """Receive a message from the frontend and forward to the comm.

        Returns:
            A tuple of (ui_element_id, state) if this is an "update" message
            and there's a ui_element_id, otherwise (None, None).
            The caller can use this to trigger a cell re-run.
        """
        if command.model_id not in self.comms:
            # Expected race: the frontend may send messages to a comm
            # that was already closed (cell re-run, server shutdown).
            LOGGER.debug(
                "Received message for unknown comm: %s", command.model_id
            )
            return (None, None)

        comm = self.comms[command.model_id]

        # Clients may write widget state, never code or style: anything
        # surviving this reaches `widget.set_state` and is echoed to
        # peers. Filter by known-key list; other underscore traits are
        # legitimate widget state.
        message = command.message
        if isinstance(message, ModelUpdateMessage):
            for key in ("_esm", "_css"):
                message.state.pop(key, None)

        comm.handle_msg(command.into_comm_payload())

        # For update messages, return ui_element_id and state for cell re-run
        if isinstance(message, ModelUpdateMessage) and comm.ui_element_id:
            return (comm.ui_element_id, message.state)

        return (None, None)


Msg = dict[str, Any]
MsgCallback = Callable[[Msg], None]
DataType = dict[str, Any] | None
MetadataType = dict[str, Any] | None
Buffer = bytes | memoryview | bytearray
BufferType = list[Buffer] | None


def _ensure_bytes(buf: object) -> bytes:
    """Coerce a buffer to plain `bytes` for msgspec serialization.

    msgspec natively handles `bytes`, `memoryview`, and `bytearray`.
    Some libraries (e.g. obstore) use custom types that hold binary data
    but aren't subclasses of these, so msgspec can't serialize them directly.

    `bytes()` handles memoryview/bytearray on all Python versions, and
    on Python 3.12+ also handles any object implementing `__buffer__`.
    """
    if isinstance(buf, bytes):
        return buf
    return bytes(buf)  # type: ignore[call-overload,no-any-return]


def _create_model_message(
    data: dict[str, Any],
    buffers: list[Buffer],
    esm_spec: EsmSpec | None = None,
) -> ModelMessage | None:
    """Create the appropriate ModelMessage based on the method field.

    Returns None for unknown methods that should be skipped. `data` is
    the ipywidgets-shaped comm payload; `esm_spec` is minted by the
    comm itself, never supplied by comm callers.

    `echo_update` is coerced to `ModelUpdate`: marimo has no echo
    protocol, and dropping echoes would lose frontend-driven trait
    changes from reconnect replay.
    """
    bbuffers = [_ensure_bytes(b) for b in buffers]
    method = data.get("method", "update")
    state = data.get("state", {})
    buffer_paths = data.get("buffer_paths", [])

    if method == "open":
        return ModelOpen(
            state=state,
            buffer_paths=buffer_paths,
            buffers=bbuffers,
            esm_spec=esm_spec,
        )
    elif method == "update":
        return ModelUpdate(
            state=state,
            buffer_paths=buffer_paths,
            buffers=bbuffers,
            esm_spec=esm_spec,
        )
    elif method == "custom":
        return ModelCustom(
            content=data.get("content"),
            buffers=bbuffers,
        )
    elif method == "echo_update":
        # Preserve frontend-driven trait changes for reconnect replay.
        # anywidget/ipywidgets can emit echo_update as the synchronisation
        # acknowledgement path; dropping it causes stale replay state.
        return ModelUpdate(
            state=state,
            buffer_paths=buffer_paths,
            buffers=bbuffers,
        )
    else:
        LOGGER.warning("Unknown method: %s, skipping", method)
        return None


# Compare to `ipykernel.comm.Comm`
#  (uses the marimo context instead of a Kernel to send/receive messages).
# Also note that `ipywidgets.widgets.Widget` is responsible to
#  calling these methods when need be.
class MarimoComm:
    # `ipywidgets.widgets.Widget` does some checks for
    # `if self.comm.kernel is not None`
    kernel = "marimo"

    def __init__(
        self,
        comm_id: WidgetModelId,
        comm_manager: MarimoCommManager,
        target_name: str,
        data: DataType = None,
        metadata: MetadataType = None,
        buffers: BufferType = None,
        **keys: object,
    ) -> None:
        del keys  # unused
        del metadata  # unused
        self._msg_callback: MsgCallback | None = None
        self._close_callback: MsgCallback | None = None
        self._closed: bool = False
        self._closed_data: dict[str, object] = {}

        self.comm_id = comm_id
        self.comm_manager = comm_manager
        self.target_name = target_name
        self.ui_element_id: str | None = None

        # Library-owned callbacks (such as anywidget's file watcher) may send
        # from a plain background thread, which has no marimo runtime context.
        # Bind the comm to the session in which it was opened so those sends
        # retain both their transport and edit/run policy.
        from marimo._runtime.context import safe_get_context
        from marimo._runtime.context.utils import get_mode

        ctx = safe_get_context()
        self._stream: Stream | None = ctx.stream if ctx is not None else None
        self._mode: RunMode | None = get_mode()
        self._open(data=data, buffers=buffers)

    def _open(
        self,
        data: DataType = None,
        buffers: BufferType = None,
    ) -> None:
        """Open the comm and send initial state.

        Mints the widget's ESM spec, kept on the comm so repr
        formatters can reference this model without re-minting.
        Traditional ipywidgets have no `_esm` and get no spec.
        """
        LOGGER.debug("Opening comm %s", self.comm_id)
        data = dict(data or {})
        state = data.get("state", {})
        self._state_serializer = AnyWidgetStateSerializer(state)
        state = self._state_serializer.serialize(state)
        if "state" in data:
            data["state"] = state
        esm = state.get("_esm")
        self.esm_spec: EsmSpec | None = (
            EsmSpec.from_esm(esm) if isinstance(esm, str) and esm else None
        )
        if self.esm_spec is not None:
            # Code travels only via the spec (see EsmSpec); copy the
            # state dict since callers may still own it.
            data["state"] = {k: v for k, v in state.items() if k != "_esm"}
        self.comm_manager.register_comm(self)
        try:
            self._broadcast(data, buffers or [], esm_spec=self.esm_spec)
            self._closed = False
        except Exception:
            self.comm_manager.unregister_comm(self)
            raise

    # Legacy method for ipywidgets compatibility
    def open(
        self,
        data: DataType = None,
        metadata: MetadataType = None,
        buffers: BufferType = None,
        **keys: object,
    ) -> None:
        del metadata, keys  # unused
        self._open(data=data, buffers=buffers)

    def send(
        self,
        data: DataType = None,
        metadata: MetadataType = None,
        buffers: BufferType = None,
    ) -> None:
        """Send a message to the frontend (state update or custom message).

        An `_esm` change (e.g. anywidget's file watcher) becomes a
        fresh spec on the update in edit sessions (hot reload) and is
        dropped everywhere else, so a viewer's widget code is immutable.
        """
        del metadata  # unused
        LOGGER.debug("Sending comm message %s", self.comm_id)
        data = dict(data or {})
        state = data.get("state")
        state = self._state_serializer.serialize(state)
        if "state" in data:
            data["state"] = state
        changed_spec: EsmSpec | None = None
        if isinstance(state, dict) and "_esm" in state:
            esm = state["_esm"]
            data["state"] = {k: v for k, v in state.items() if k != "_esm"}
            if self._mode == "edit" and isinstance(esm, str) and esm:
                self.esm_spec = EsmSpec.from_esm(esm)
                changed_spec = self.esm_spec
        self._broadcast(data, buffers or [], esm_spec=changed_spec)

    def close(
        self,
        data: DataType = None,
        metadata: MetadataType = None,
        buffers: BufferType = None,
        deleting: bool = False,
    ) -> None:
        """Close the comm."""
        del data, metadata, buffers  # unused for close
        LOGGER.debug("Closing comm %s", self.comm_id)
        if self._closed:
            return
        self._closed = True

        broadcast_notification(
            ModelLifecycleNotification(
                model_id=self.comm_id,
                message=ModelClose(),
            ),
            stream=self._stream,
        )

        if not deleting:
            self.comm_manager.unregister_comm(self)

    def __del__(self) -> None:
        self.close(deleting=True)

    def _broadcast(
        self,
        data: dict[str, Any],
        buffers: list[Buffer],
        esm_spec: EsmSpec | None = None,
    ) -> None:
        """Broadcast a model lifecycle notification."""
        message = _create_model_message(data, buffers, esm_spec=esm_spec)
        if message is None:
            return
        broadcast_notification(
            ModelLifecycleNotification(
                model_id=self.comm_id,
                message=message,
            ),
            stream=self._stream,
        )

    # This is the method that ipywidgets.widgets.Widget uses to respond to
    # client-side changes
    def on_msg(self, callback: MsgCallback) -> None:
        self._msg_callback = callback

    def on_close(self, callback: MsgCallback) -> None:
        self._close_callback = callback

    def handle_msg(self, msg: Msg) -> None:
        LOGGER.debug("Handling message for comm %s", self.comm_id)
        if self._msg_callback is not None:
            self._msg_callback(msg)
        else:
            LOGGER.warning(
                "Received message for comm %s but no callback registered",
                self.comm_id,
            )

    def handle_close(self, msg: Msg) -> None:
        if self._close_callback is not None:
            self._close_callback(msg)
        else:
            LOGGER.debug(
                "Received close for comm %s but no callback registered",
                self.comm_id,
            )
