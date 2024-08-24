# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
from typing import Any, Callable, Dict, List, Optional


class MarimoCommManager:
    comms: Dict[str, "MarimoComm"] = {}

    def register_comm(self, comm: "MarimoComm") -> str:
        comm_id = comm.comm_id
        self.comms[comm_id] = comm
        return comm_id

    def unregister_comm(self, comm: "MarimoComm") -> "MarimoComm":
        return self.comms.pop(comm.comm_id)


MsgCallback = Callable[[Dict[str, object]], None]
DataType = Optional[Dict[str, object]]
MetadataType = Optional[Dict[str, object]]
BufferType = Optional[List[bytes]]

COMM_MESSAGE_NAME = "marimo_comm_msg"
COMM_OPEN_NAME = "marimo_comm_open"
COMM_CLOSE_NAME = "marimo_comm_close"


# Compare to `ipykernel.comm.Comm`
#  (uses the marimo context instead of a Kernel to send/receive messages).
# Also note that `ipywidgets.widgets.Widget` is responsible to
#  calling these methods when need be.
class MarimoComm:
    # `ipywidgets.widgets.Widget` does some checks for
    # `if self.comm.kernel is not None`
    kernel = "marimo"

    _msg_callback: Optional[MsgCallback]
    _close_callback: Optional[MsgCallback]
    _closed: bool = False
    _closed_data: Dict[str, object] = {}

    def __init__(
        self,
        comm_id: str,
        comm_manager: MarimoCommManager,
        target_name: str,
        data: DataType = None,
        metadata: MetadataType = None,
        buffers: BufferType = None,
        **keys: object,
    ) -> None:
        self.comm_id = comm_id
        self.comm_manager = comm_manager
        self.target_name = target_name
        self.open(data=data, metadata=metadata, buffers=buffers, **keys)
        self.ui_element_id: Optional[str] = None
        self._publish_message_buffer: list[Any] = []

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

        if msg_type == COMM_MESSAGE_NAME:
            self._publish_message_buffer.append((data, metadata, buffers))
            self.flush()

    def flush(self) -> None:
        if not self.ui_element_id:
            return

        from marimo._messaging.ops import SendUIElementMessage

        while self._publish_message_buffer:
            data, _metadata, buffers = self._publish_message_buffer.pop(0)

            SendUIElementMessage(
                ui_element=self.ui_element_id,
                message=data,
                buffers=[
                    base64.b64encode(buffer).decode() for buffer in buffers
                ],
            ).broadcast()

    # This is the method that ipywidgets.widgets.Widget uses to respond to
    # client-side changes
    def on_msg(self, callback: MsgCallback) -> None:
        self._msg_callback = callback

    def on_close(self, callback: MsgCallback) -> None:
        self._close_callback = callback

    def handle_msg(self, msg: Dict[str, object]) -> None:
        if self._msg_callback is not None:
            self._msg_callback(msg)

    def handle_close(self, msg: Dict[str, object]) -> None:
        if self._close_callback is not None:
            self._close_callback(msg)
