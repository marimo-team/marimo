from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from marimo._plugins.ui._impl.comm import (
    MarimoComm,
    MarimoCommManager,
)
from marimo._runtime.commands import (
    ModelCommand,
    ModelCustomMessage,
    ModelUpdateMessage,
)
from marimo._types.ids import WidgetModelId


@pytest.fixture
def comm_manager():
    return MarimoCommManager()


@pytest.fixture
def comm(comm_manager: MarimoCommManager) -> MarimoComm:
    comm_id = WidgetModelId("test-comm")
    with patch("marimo._plugins.ui._impl.comm.broadcast_notification"):
        return MarimoComm(
            comm_id=comm_id,
            comm_manager=comm_manager,
            target_name="test_target",
        )


def test_comm_manager_register_unregister(
    comm_manager: MarimoCommManager, comm: MarimoComm
):
    # comm is already registered during __init__
    comm_id = comm.comm_id
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
        command = ModelCommand(
            model_id=WidgetModelId("unknown"),
            message=ModelUpdateMessage(state={}, buffer_paths=[]),
            buffers=[],
        )
        comm_manager.receive_comm_message(command)
        mock_logger.warning.assert_called_once()


def test_comm_initialization(comm: MarimoComm):
    assert comm.comm_id == WidgetModelId("test-comm")
    assert comm.target_name == "test_target"
    assert comm.kernel == "marimo"
    assert not comm._closed
    assert comm._msg_callback is None
    assert comm._close_callback is None


def test_comm_open(comm: MarimoComm):
    with patch.object(comm, "_broadcast") as mock_broadcast:
        comm.open(data={"test": "data"})
        mock_broadcast.assert_called_once_with({"test": "data"}, [])
        assert not comm._closed


def test_comm_send(comm: MarimoComm):
    with patch.object(comm, "_broadcast") as mock_broadcast:
        comm.send(data={"test": "data"})
        mock_broadcast.assert_called_once_with({"test": "data"}, [])


def test_comm_close(comm: MarimoComm):
    with patch(
        "marimo._plugins.ui._impl.comm.broadcast_notification"
    ) as mock_broadcast:
        comm.close(data={"test": "data"})
        mock_broadcast.assert_called_once()
        assert comm._closed


def test_comm_close_already_closed(comm: MarimoComm):
    comm._closed = True
    with patch(
        "marimo._plugins.ui._impl.comm.broadcast_notification"
    ) as mock_broadcast:
        comm.close()
        mock_broadcast.assert_not_called()


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
        mock_logger.debug.assert_called()


def test_comm_broadcast(comm: MarimoComm):
    """Test that _broadcast sends a ModelLifecycleNotification."""
    with patch(
        "marimo._plugins.ui._impl.comm.broadcast_notification"
    ) as mock_broadcast:
        comm._broadcast({"method": "update", "state": {"key": "value"}}, [])
        mock_broadcast.assert_called_once()
        notification = mock_broadcast.call_args[0][0]
        assert notification.model_id == comm.comm_id


def test_comm_manager_receive_update_message(
    comm_manager: MarimoCommManager, comm: MarimoComm
):
    """Test receiving an update message through the comm manager."""
    callback = MagicMock()
    comm.on_msg(callback)
    comm.ui_element_id = "test-element"

    command = ModelCommand(
        model_id=comm.comm_id,
        message=ModelUpdateMessage(
            state={"key": "value"},
            buffer_paths=[],
        ),
        buffers=[],
    )
    result = comm_manager.receive_comm_message(command)
    assert result == ("test-element", {"key": "value"})
    callback.assert_called_once()


def test_comm_manager_receive_custom_message(
    comm_manager: MarimoCommManager, comm: MarimoComm
):
    """Test receiving a custom message through the comm manager."""
    callback = MagicMock()
    comm.on_msg(callback)

    command = ModelCommand(
        model_id=comm.comm_id,
        message=ModelCustomMessage(
            content={"custom": "data"},
        ),
        buffers=[],
    )
    result = comm_manager.receive_comm_message(command)
    assert result == (None, None)
    callback.assert_called_once()
