from unittest.mock import MagicMock, patch

import pytest

from marimo._plugins.ui._impl.comm import (
    COMM_CLOSE_NAME,
    COMM_MESSAGE_NAME,
    COMM_OPEN_NAME,
    MarimoComm,
    MarimoCommManager,
    MessageBufferData,
)
from marimo._types.ids import WidgetModelId


@pytest.fixture
def comm_manager():
    return MarimoCommManager()


@pytest.fixture
def comm(comm_manager: MarimoCommManager) -> MarimoComm:
    comm_id = WidgetModelId("test-comm")
    return MarimoComm(
        comm_id=comm_id,
        comm_manager=comm_manager,
        target_name="test_target",
    )


def test_comm_manager_register_unregister(
    comm_manager: MarimoCommManager, comm: MarimoComm
):
    # Test registration
    comm_id = comm_manager.register_comm(comm)
    assert comm_id in comm_manager.comms
    assert comm_manager.comms[comm_id] == comm

    # Test unregistration
    unregistered_comm = comm_manager.unregister_comm(comm)
    assert unregistered_comm == comm
    assert comm_id not in comm_manager.comms


def test_comm_manager_receive_unknown_message(
    comm_manager: MarimoCommManager,
):
    with patch("marimo._plugins.ui._impl.comm.LOGGER") as mock_logger:
        comm_manager.receive_comm_message(
            WidgetModelId("unknown"),
            MagicMock(),
            None,
        )
        mock_logger.warning.assert_called_once()


def test_comm_initialization(comm: MarimoComm):
    assert comm.comm_id == WidgetModelId("test-comm")
    assert comm.target_name == "test_target"
    assert comm.kernel == "marimo"
    assert not comm._closed
    assert comm._msg_callback is None
    assert comm._close_callback is None


def test_comm_open(comm: MarimoComm):
    with patch.object(comm, "_publish_msg") as mock_publish:
        comm.open(data={"test": "data"})
        mock_publish.assert_called_once_with(
            COMM_OPEN_NAME,
            data={"test": "data"},
            metadata=None,
            buffers=None,
            target_name="test_target",
            target_module=None,
        )
        assert not comm._closed


def test_comm_send(comm: MarimoComm):
    with patch.object(comm, "_publish_msg") as mock_publish:
        comm.send(data={"test": "data"})
        mock_publish.assert_called_once_with(
            COMM_MESSAGE_NAME,
            data={"test": "data"},
            metadata=None,
            buffers=None,
        )


def test_comm_close(comm: MarimoComm):
    with patch.object(comm, "_publish_msg") as mock_publish:
        comm.close(data={"test": "data"})
        mock_publish.assert_called_once_with(
            COMM_CLOSE_NAME,
            data={"test": "data"},
            metadata=None,
            buffers=None,
        )
        assert comm._closed


def test_comm_close_already_closed(comm: MarimoComm):
    comm._closed = True
    with patch.object(comm, "_publish_msg") as mock_publish:
        comm.close()
        mock_publish.assert_not_called()


def test_comm_on_msg(comm: MarimoComm):
    callback = MagicMock()
    comm.on_msg(callback)
    assert comm._msg_callback == callback


def test_comm_on_close(comm: MarimoComm):
    callback = MagicMock()
    comm.on_close(callback)
    assert comm._close_callback == callback


def test_comm_handle_msg(comm: MarimoComm):
    callback = MagicMock()
    comm.on_msg(callback)
    msg = {"test": "message"}
    comm.handle_msg(msg)
    callback.assert_called_once_with(msg)


def test_comm_handle_msg_no_callback(comm: MarimoComm):
    with patch("marimo._plugins.ui._impl.comm.LOGGER") as mock_logger:
        msg = {"test": "message"}
        comm.handle_msg(msg)
        mock_logger.warning.assert_called_once()


def test_comm_handle_close(comm: MarimoComm):
    callback = MagicMock()
    comm.on_close(callback)
    msg = {"test": "message"}
    comm.handle_close(msg)
    callback.assert_called_once_with(msg)


def test_comm_handle_close_no_callback(comm: MarimoComm):
    with patch("marimo._plugins.ui._impl.comm.LOGGER") as mock_logger:
        msg = {"test": "message"}
        comm.handle_close(msg)
        mock_logger.warning.assert_called_once()


def test_comm_flush(comm: MarimoComm):
    test_data = {"test": "data"}
    test_metadata = {"meta": "data"}
    test_buffers = [b"test_buffer"]

    comm._publish_message_buffer.append(
        MessageBufferData(
            data=test_data,
            metadata=test_metadata,
            buffers=test_buffers,
            model_id=comm.comm_id,
        )
    )

    with patch("marimo._messaging.ops.SendUIElementMessage") as mock_send:
        comm.flush()
        mock_send.assert_called_once()
        call_args = mock_send.call_args[1]
        assert call_args["model_id"] == comm.comm_id
        assert call_args["message"] == test_data
        assert len(call_args["buffers"]) == 1
        assert (
            call_args["buffers"][0] == "dGVzdF9idWZmZXI="
        )  # base64 of b"test_buffer"
