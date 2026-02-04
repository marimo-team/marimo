# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional, cast

from marimo._loggers import marimo_logger
from marimo._messaging.notification import (
    ModelClose,
    ModelCustom,
    ModelLifecycleNotification,
    ModelMessage,
    ModelOpen,
    ModelUpdate,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._types.ids import WidgetModelId

if TYPE_CHECKING:
    from marimo._plugins.ui._impl.anywidget.types import (
        TypedModelMessagePayload,
    )

from marimo._runtime.commands import (
    ModelCustomMessage,
    ModelMessage as ModelMessageCommand,
    ModelUpdateMessage,
)

LOGGER = marimo_logger()


class MarimoCommManager:
    comms: dict[WidgetModelId, MarimoComm] = {}

    def register_comm(self, comm: MarimoComm) -> str:
        comm_id = comm.comm_id
        self.comms[comm_id] = comm
        return comm_id

    def unregister_comm(self, comm: MarimoComm) -> MarimoComm:
        return self.comms.pop(comm.comm_id)

    def receive_comm_message(
        self,
        comm_id: WidgetModelId,
        message: ModelMessageCommand,
        buffers: list[bytes],
    ) -> tuple[Optional[str], Optional[dict[str, Any]]]:
        """Receive a message from the frontend and forward to the comm.

        Returns:
            A tuple of (ui_element_id, state) if this is an "update" message
            and there's a ui_element_id, otherwise (None, None).
            The caller can use this to trigger a cell re-run.
        """
        if comm_id not in self.comms:
            LOGGER.warning("Received message for unknown comm: %s", comm_id)
            return (None, None)

        comm = self.comms[comm_id]

        # Build the message payload based on message type
        if isinstance(message, ModelUpdateMessage):
            msg: TypedModelMessagePayload = {
                "content": {
                    "data": {
                        "method": "update",
                        "state": message.state,
                        "buffer_paths": message.buffer_paths,
                    }
                },
                "buffers": buffers,
            }
            # Forward to the comm's message handler
            comm.handle_msg(cast(Msg, msg))
            # For update messages, return ui_element_id and state for cell re-run
            if comm.ui_element_id:
                return (comm.ui_element_id, message.state)
        elif isinstance(message, ModelCustomMessage):
            msg = {
                "content": {
                    "data": {
                        "method": "custom",
                        "content": message.content,
                    }
                },
                "buffers": buffers,
            }
            comm.handle_msg(cast(Msg, msg))

        return (None, None)


Msg = dict[str, Any]
MsgCallback = Callable[[Msg], None]
DataType = Optional[dict[str, Any]]
MetadataType = Optional[dict[str, Any]]
BufferType = Optional[list[bytes]]


def _create_model_message(
    data: dict[str, Any],
    buffers: list[bytes],
) -> Optional[ModelMessage]:
    """Create the appropriate ModelMessage based on the method field.

    Returns None for methods that should be skipped (e.g., echo_update).
    """
    method = data.get("method", "update")
    state = data.get("state", {})
    buffer_paths = data.get("buffer_paths", [])

    if method == "open":
        return ModelOpen(
            state=state,
            buffer_paths=buffer_paths,
            buffers=buffers,
        )
    elif method == "update":
        return ModelUpdate(
            state=state,
            buffer_paths=buffer_paths,
            buffers=buffers,
        )
    elif method == "custom":
        return ModelCustom(
            content=data.get("content"),
            buffers=buffers,
        )
    elif method == "echo_update":
        # echo_update is for multi-client sync acknowledgment, skip it
        return None
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
        self._msg_callback: Optional[MsgCallback] = None
        self._close_callback: Optional[MsgCallback] = None
        self._closed: bool = False
        self._closed_data: dict[str, object] = {}

        self.comm_id = comm_id
        self.comm_manager = comm_manager
        self.target_name = target_name
        self.ui_element_id: Optional[str] = None
        self._open(data=data, buffers=buffers)

    def _open(
        self,
        data: DataType = None,
        buffers: BufferType = None,
    ) -> None:
        """Open the comm and send initial state."""
        LOGGER.debug("Opening comm %s", self.comm_id)
        self.comm_manager.register_comm(self)
        try:
            self._broadcast(data or {}, buffers or [])
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
        """Send a message to the frontend (state update or custom message)."""
        del metadata  # unused
        LOGGER.debug("Sending comm message %s", self.comm_id)
        self._broadcast(data or {}, buffers or [])

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
            )
        )

        if not deleting:
            self.comm_manager.unregister_comm(self)

    def __del__(self) -> None:
        self.close(deleting=True)

    def _broadcast(self, data: dict[str, Any], buffers: list[bytes]) -> None:
        """Broadcast a model lifecycle notification."""
        message = _create_model_message(data, buffers)
        if message is None:
            return
        broadcast_notification(
            ModelLifecycleNotification(
                model_id=self.comm_id,
                message=message,
            )
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
