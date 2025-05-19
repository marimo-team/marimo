# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

from marimo._loggers import marimo_logger
from marimo._types.ids import WidgetModelId

if TYPE_CHECKING:
    from marimo._plugins.ui._impl.anywidget.types import (
        TypedModelMessagePayload,
    )
    from marimo._runtime.requests import ModelMessage

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
        message: ModelMessage,
        buffers: Optional[list[bytes]],
    ) -> None:
        if comm_id not in self.comms:
            LOGGER.warning("Received message for unknown comm", comm_id)
            return

        comm = self.comms[comm_id]

        msg: TypedModelMessagePayload = {
            "content": {
                "data": {
                    "state": message.state,
                    "method": "update",
                    "buffer_paths": message.buffer_paths,
                }
            },
            "buffers": buffers or [],
        }

        comm.handle_msg(cast(Msg, msg))


Msg = dict[str, Any]
MsgCallback = Callable[[Msg], None]
DataType = Optional[dict[str, Any]]
MetadataType = Optional[dict[str, Any]]
BufferType = Optional[list[bytes]]

COMM_MESSAGE_NAME = "marimo_comm_msg"
COMM_OPEN_NAME = "marimo_comm_open"
COMM_CLOSE_NAME = "marimo_comm_close"


@dataclass
class MessageBufferData:
    data: dict[str, Any]
    metadata: dict[str, Any]
    buffers: list[bytes]
    model_id: WidgetModelId


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
        self._msg_callback: Optional[MsgCallback] = None
        self._close_callback: Optional[MsgCallback] = None
        self._closed: bool = False
        self._closed_data: dict[str, object] = {}

        self.comm_id = comm_id
        self.comm_manager = comm_manager
        self.target_name = target_name
        self.ui_element_id: Optional[str] = None
        self._publish_message_buffer: list[MessageBufferData] = []
        self.open(data=data, metadata=metadata, buffers=buffers, **keys)

    def open(
        self,
        data: DataType = None,
        metadata: MetadataType = None,
        buffers: BufferType = None,
        **keys: object,
    ) -> None:
        self.comm_manager.register_comm(self)
        try:
            self._publish_msg(
                COMM_OPEN_NAME,
                data=data,
                metadata=metadata,
                buffers=buffers,
                target_name=self.target_name,
                target_module=None,
                **keys,
            )
            self._closed = False
        except Exception:
            self.comm_manager.unregister_comm(self)
            raise

    # Inform client of any mutation(s) to the model
    # (e.g., add a marker to a map, without a full redraw)
    def send(
        self,
        data: DataType = None,
        metadata: MetadataType = None,
        buffers: BufferType = None,
    ) -> None:
        self._publish_msg(
            COMM_MESSAGE_NAME,
            data=data,
            metadata=metadata,
            buffers=buffers,
        )

    def close(
        self,
        data: DataType = None,
        metadata: MetadataType = None,
        buffers: BufferType = None,
        deleting: bool = False,
    ) -> None:
        if self._closed:
            return
        self._closed = True
        data = self._closed_data if data is None else data
        self._publish_msg(
            COMM_CLOSE_NAME,
            data=data,
            metadata=metadata,
            buffers=buffers,
        )
        if not deleting:
            # If deleting, the comm can't be unregistered
            self.comm_manager.unregister_comm(self)

    # trigger close on gc
    def __del__(self) -> None:
        self.close(deleting=True)

    # Compare to `ipykernel.comm.Comm._publish_msg`, but...
    # https://github.com/jupyter/jupyter_client/blob/c5c0b80/jupyter_client/session.py#L749
    # ...the real meat of the implement
    #   is in `jupyter_client.session.Session.send`
    # https://github.com/jupyter/jupyter_client/blob/c5c0b8/jupyter_client/session.py#L749-L862
    def _publish_msg(
        self,
        msg_type: str,
        data: DataType = None,
        metadata: MetadataType = None,
        buffers: BufferType = None,
        **keys: object,
    ) -> None:
        del keys
        data = {} if data is None else data
        metadata = {} if metadata is None else metadata
        buffers = [] if buffers is None else buffers

        if msg_type == COMM_OPEN_NAME:
            self._publish_message_buffer.append(
                MessageBufferData(
                    data, metadata, buffers, model_id=self.comm_id
                )
            )
            self.flush()
            return

        if msg_type == COMM_MESSAGE_NAME:
            self._publish_message_buffer.append(
                MessageBufferData(
                    data, metadata, buffers, model_id=self.comm_id
                )
            )
            self.flush()
            return

        if msg_type == COMM_CLOSE_NAME:
            self._publish_message_buffer.append(
                MessageBufferData(
                    data, metadata, buffers, model_id=self.comm_id
                )
            )
            self.flush()
            return

        LOGGER.warning(
            "Unknown message type",
            msg_type,
            data,
        )

    def flush(self) -> None:
        from marimo._messaging.ops import SendUIElementMessage

        while self._publish_message_buffer:
            item = self._publish_message_buffer.pop(0)
            SendUIElementMessage(
                # ui_element_id can be None. In this case, we are creating a model
                # not tied to a specific UI element
                ui_element=self.ui_element_id,
                model_id=item.model_id,
                message=item.data,
                buffers=[
                    base64.b64encode(buffer).decode()
                    for buffer in item.buffers
                ],
            ).broadcast()

    # This is the method that ipywidgets.widgets.Widget uses to respond to
    # client-side changes
    def on_msg(self, callback: MsgCallback) -> None:
        self._msg_callback = callback

    def on_close(self, callback: MsgCallback) -> None:
        self._close_callback = callback

    def handle_msg(self, msg: Msg) -> None:
        if self._msg_callback is not None:
            self._msg_callback(msg)
        else:
            LOGGER.warning(
                "Received message for comm but no callback registered",
                self.comm_id,
                msg,
            )

    def handle_close(self, msg: Msg) -> None:
        if self._close_callback is not None:
            self._close_callback(msg)
        else:
            LOGGER.warning(
                "Received close for comm but no callback registered",
                self.comm_id,
                msg,
            )
