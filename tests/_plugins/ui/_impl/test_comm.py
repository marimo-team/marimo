from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from marimo._plugins.ui._impl.anywidget.init import CommLifecycleItem
from marimo._plugins.ui._impl.anywidget.widget_ref import (
    AnyWidgetStateSerializer,
)
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
        c = MarimoComm(
            comm_id=comm_id,
            comm_manager=comm_manager,
            target_name="test_target",
        )
    yield c  # type: ignore[misc]
    # Ensure the comm is closed so __del__ doesn't fire broadcast_notification
    # during garbage collection in a later test's patch scope.
    with patch("marimo._plugins.ui._impl.comm.broadcast_notification"):
        c._closed = True


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
        mock_logger.debug.assert_called_once()


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
        mock_broadcast.assert_called_once_with(
            {"test": "data"}, [], esm_spec=None
        )
        assert not comm._closed


def test_comm_send(comm: MarimoComm):
    with patch.object(comm, "_broadcast") as mock_broadcast:
        comm.send(data={"test": "data"})
        mock_broadcast.assert_called_once_with(
            {"test": "data"}, [], esm_spec=None
        )


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


def test_comm_drops_echo_update(comm: MarimoComm):
    """echo_update (ipywidgets' ack of a client write) is never broadcast."""
    with patch(
        "marimo._plugins.ui._impl.comm.broadcast_notification"
    ) as mock_broadcast:
        comm._broadcast(
            {"method": "echo_update", "state": {"key": "value"}},
            [],
        )
        mock_broadcast.assert_not_called()


def test_client_update_is_not_echoed_back(
    comm_manager: MarimoCommManager, comm: MarimoComm
):
    """A client write must not bounce back as a live update.

    Simulates ipywidgets' `Widget.set_state`, which acks a client
    update with `echo_update` before observers send genuine updates.
    Guarantees an echo is sent, unlike the real-stack test in
    test_anywidget.py, where echoing is up to ipywidgets.
    """

    def fake_set_state(msg: dict) -> None:
        state = msg["content"]["data"]["state"]
        # ipywidgets acks the client's own values first...
        comm.send({"method": "echo_update", "state": state})
        # ...then an observer reacts with a kernel-driven change.
        comm.send({"method": "update", "state": {"chart": "<new svg>"}})

    comm.on_msg(fake_set_state)
    command = ModelCommand(
        model_id=comm.comm_id,
        message=ModelUpdateMessage(state={"slider": 5}, buffer_paths=[]),
        buffers=[],
    )
    with patch(
        "marimo._plugins.ui._impl.comm.broadcast_notification"
    ) as mock_broadcast:
        comm_manager.receive_comm_message(command)
        # Exactly one broadcast: the observer's update. The echo of
        # {"slider": 5} is dropped.
        mock_broadcast.assert_called_once()
        notification = mock_broadcast.call_args[0][0]
        assert notification.message.state == {"chart": "<new svg>"}


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


def test_comm_lifecycle_item_dispose_closes_comm(
    comm_manager: MarimoCommManager, comm: MarimoComm
):
    """CommLifecycleItem.dispose() should close the comm."""
    item = CommLifecycleItem(comm)
    assert not comm._closed
    assert comm.comm_id in comm_manager.comms

    with patch(
        "marimo._plugins.ui._impl.comm.broadcast_notification"
    ) as mock_broadcast:
        result = item.dispose(context=MagicMock(), deletion=False)

    assert result is True
    assert comm._closed
    assert comm.comm_id not in comm_manager.comms
    mock_broadcast.assert_called_once()


class _CustomBytes:
    """Simulates obstore.Bytes — implements buffer protocol but not a
    subclass of bytes/memoryview/bytearray."""

    def __init__(self, data: bytes):
        self._data = data

    def __buffer__(self, flags: int = 0) -> memoryview:
        return memoryview(self._data)


class TestBroadcastBufferTypes:
    """Broadcast through the comm with various buffer types and verify the
    notification carries the right data after a serialize/deserialize
    roundtrip."""

    PAYLOAD = b"RIFF\x00\x01binary\xff\xfe"

    def _roundtrip_buffer(self, comm, buf):
        """Broadcast a buffer through the comm and return the deserialized
        notification."""
        from marimo._messaging.notification import ModelLifecycleNotification
        from marimo._messaging.serde import (
            deserialize_kernel_message,
            serialize_kernel_message,
        )

        with patch(
            "marimo._plugins.ui._impl.comm.broadcast_notification"
        ) as mock_broadcast:
            comm._broadcast(
                {"method": "update", "state": {}, "buffer_paths": []},
                [buf],
            )
            notification = mock_broadcast.call_args[0][0]

        assert isinstance(notification, ModelLifecycleNotification)
        # Full roundtrip through JSON serialization
        raw = serialize_kernel_message(notification)
        return deserialize_kernel_message(raw)

    def test_bytes_buffer(self, comm):
        result = self._roundtrip_buffer(comm, self.PAYLOAD)
        assert result.message.buffers == [self.PAYLOAD]

    def test_memoryview_buffer(self, comm):
        result = self._roundtrip_buffer(comm, memoryview(self.PAYLOAD))
        assert result.message.buffers == [self.PAYLOAD]

    def test_bytearray_buffer(self, comm):
        result = self._roundtrip_buffer(comm, bytearray(self.PAYLOAD))
        assert result.message.buffers == [self.PAYLOAD]

    @pytest.mark.skipif(
        sys.version_info < (3, 12),
        reason="__buffer__ dunder requires Python 3.12+",
    )
    def test_custom_buffer_protocol(self, comm):
        """Custom buffer-protocol objects (like obstore.Bytes) survive the
        roundtrip."""
        result = self._roundtrip_buffer(comm, _CustomBytes(self.PAYLOAD))
        assert result.message.buffers == [self.PAYLOAD]

    def test_unsupported_type_raises(self):
        from marimo._plugins.ui._impl.comm import _ensure_bytes

        with pytest.raises(TypeError):
            _ensure_bytes("not bytes")


class TestEsmSpecMinting:
    """`_open` mints the ESM spec — the only channel widget code takes
    to the frontend."""

    ESM = "export default { render({ model, el }) {} }"

    def _open_comm(self, comm_manager, state):
        """Open a comm with `state` and return (comm, broadcast message)."""
        with patch(
            "marimo._plugins.ui._impl.comm.broadcast_notification"
        ) as mock_broadcast:
            comm = MarimoComm(
                comm_id=WidgetModelId("esm-test"),
                comm_manager=comm_manager,
                target_name="jupyter.widget",
                data={"state": state, "buffer_paths": [], "method": "open"},
            )
            notification = mock_broadcast.call_args[0][0]
        # Prevent __del__ from broadcasting outside the patch scope.
        comm._closed = True
        return comm, notification.message

    def test_inline_esm_is_minted_and_stripped(self, comm_manager):
        from marimo._utils.code import hash_code

        state = {"_esm": self.ESM, "count": 1}
        comm, message = self._open_comm(comm_manager, state)

        assert message.esm_spec is not None
        # Without a runtime context, virtual files degrade to data URLs
        # (see VirtualFile.create_and_register); in a live kernel this
        # is a ./@file/ URL instead. Either way it is importable.
        assert message.esm_spec.url.startswith("data:")
        assert message.esm_spec.hash == hash_code(self.ESM)
        # Code must not travel in state; everything else must.
        assert "_esm" not in message.state
        assert message.state["count"] == 1
        # The comm keeps the spec for repr formatters.
        assert comm.esm_spec == message.esm_spec

    def test_url_form_esm_passes_through(self, comm_manager):
        from marimo._utils.code import hash_code

        url = "https://esm.sh/some-widget@1.0.0"
        _, message = self._open_comm(comm_manager, {"_esm": url})

        assert message.esm_spec is not None
        assert message.esm_spec.url == url
        assert message.esm_spec.hash == hash_code(url)

    def test_no_esm_means_no_spec(self, comm_manager):
        comm, message = self._open_comm(comm_manager, {"value": 5})

        assert message.esm_spec is None
        assert comm.esm_spec is None
        assert message.state == {"value": 5}

    def test_empty_esm_means_no_spec(self, comm_manager):
        _, message = self._open_comm(comm_manager, {"_esm": ""})
        assert message.esm_spec is None

    def test_caller_state_is_not_mutated(self, comm_manager):
        # ipywidgets may still own the state dict it hands to open();
        # stripping must happen on a copy.
        state = {"_esm": self.ESM, "count": 1}
        self._open_comm(comm_manager, state)
        assert state["_esm"] == self.ESM

    def test_spec_survives_serde_roundtrip(self, comm_manager):
        from marimo._messaging.serde import (
            deserialize_kernel_message,
            serialize_kernel_message,
        )

        with patch(
            "marimo._plugins.ui._impl.comm.broadcast_notification"
        ) as mock_broadcast:
            comm = MarimoComm(
                comm_id=WidgetModelId("esm-roundtrip"),
                comm_manager=comm_manager,
                target_name="jupyter.widget",
                data={
                    "state": {"_esm": self.ESM},
                    "buffer_paths": [],
                    "method": "open",
                },
            )
            notification = mock_broadcast.call_args[0][0]
        comm._closed = True

        result = deserialize_kernel_message(
            serialize_kernel_message(notification)
        )
        assert result.message.esm_spec == notification.message.esm_spec


@dataclass(frozen=True)
class _ModelIdWidget:
    """Minimal ipywidgets-backed anywidget shape for wire transport tests."""

    model_id: str


class TestAnywidgetWireReferences:
    ESM = "export default { render() {} }"

    def test_plain_state_does_not_import_optional_anywidget(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for module_name in list(sys.modules):
            if module_name == "anywidget" or module_name.startswith(
                "anywidget."
            ):
                monkeypatch.delitem(sys.modules, module_name)

        serializer = AnyWidgetStateSerializer({"_esm": self.ESM})
        state = {"count": 1, "label": "counter"}

        assert serializer.serialize(state) is state
        assert "anywidget" not in sys.modules

    def test_model_open_replaces_direct_and_nested_widget_refs(
        self, comm_manager: MarimoCommManager
    ) -> None:
        from marimo._messaging.serde import (
            deserialize_kernel_message,
            serialize_kernel_message,
        )

        child = _ModelIdWidget("child-open")
        with patch(
            "marimo._plugins.ui._impl.comm.broadcast_notification"
        ) as mock_broadcast:
            comm = MarimoComm(
                comm_id=WidgetModelId("parent-open"),
                comm_manager=comm_manager,
                target_name="jupyter.widget",
                data={
                    "state": {
                        "_esm": self.ESM,
                        "child": child,
                        "layout": {"items": [child, {"nested": child}]},
                    },
                    "buffer_paths": [],
                    "method": "open",
                },
            )
            notification = mock_broadcast.call_args[0][0]
        comm._closed = True

        expected_state = {
            "child": "anywidget:child-open",
            "layout": {
                "items": [
                    "anywidget:child-open",
                    {"nested": "anywidget:child-open"},
                ]
            },
        }
        assert notification.message.state == expected_state

        roundtripped = deserialize_kernel_message(
            serialize_kernel_message(notification)
        )
        assert roundtripped.message.state == expected_state

    def test_model_update_replaces_reassigned_widget_ref(
        self, comm_manager: MarimoCommManager
    ) -> None:
        replacement = _ModelIdWidget("child-update")
        with patch(
            "marimo._plugins.ui._impl.comm.broadcast_notification"
        ) as mock_broadcast:
            comm = MarimoComm(
                comm_id=WidgetModelId("parent-update"),
                comm_manager=comm_manager,
                target_name="jupyter.widget",
                data={
                    "state": {"_esm": self.ESM},
                    "buffer_paths": [],
                    "method": "open",
                },
            )
            mock_broadcast.reset_mock()
            comm.send(
                data={
                    "state": {"child": replacement},
                    "buffer_paths": [],
                    "method": "update",
                }
            )
            notification = mock_broadcast.call_args[0][0]
        comm._closed = True

        assert notification.message.state == {
            "child": "anywidget:child-update"
        }


def test_comm_lifecycle_item_dispose_idempotent(comm: MarimoComm):
    """Calling dispose twice should not error (comm.close is idempotent)."""
    item = CommLifecycleItem(comm)

    with patch("marimo._plugins.ui._impl.comm.broadcast_notification"):
        item.dispose(context=MagicMock(), deletion=False)
        # Second dispose — comm is already closed, should be a no-op
        result = item.dispose(context=MagicMock(), deletion=True)

    assert result is True
    assert comm._closed


class TestEsmHotReload:
    """`send` intercepts `_esm` in updates: a code change on a live
    model becomes a fresh spec in edit sessions and is dropped
    everywhere else."""

    ESM_V2 = "export default { render({ model, el }) { /* v2 */ } }"

    def _send_update(self, comm_manager, mode):
        with patch(
            "marimo._plugins.ui._impl.comm.broadcast_notification"
        ) as mock_broadcast:
            with patch(
                "marimo._runtime.context.utils.get_mode", return_value=mode
            ):
                comm = MarimoComm(
                    comm_id=WidgetModelId("hmr-test"),
                    comm_manager=comm_manager,
                    target_name="jupyter.widget",
                    data={
                        "state": {"_esm": "export default {}"},
                        "buffer_paths": [],
                        "method": "open",
                    },
                )
            comm.send(
                data={
                    "state": {"_esm": self.ESM_V2, "count": 1},
                    "buffer_paths": [],
                    "method": "update",
                }
            )
            update = mock_broadcast.call_args[0][0].message
        comm._closed = True
        return comm, update

    def test_edit_mode_mints_new_spec(self, comm_manager):
        from marimo._utils.code import hash_code

        comm, update = self._send_update(comm_manager, "edit")
        assert "_esm" not in update.state
        assert update.state["count"] == 1
        assert update.esm_spec is not None
        assert update.esm_spec.hash == hash_code(self.ESM_V2)
        # The comm's spec follows the live code so late repr formatters
        # and replay see the current generation.
        assert comm.esm_spec == update.esm_spec

    def test_run_mode_drops_code_entirely(self, comm_manager):
        from marimo._utils.code import hash_code

        comm, update = self._send_update(comm_manager, "run")
        assert "_esm" not in update.state
        assert update.state["count"] == 1
        # Viewers' widget code is immutable for the model's lifetime.
        assert update.esm_spec is None
        assert comm.esm_spec is not None
        assert comm.esm_spec.hash == hash_code("export default {}")

    def test_plain_thread_send_uses_creation_session(
        self, executing_kernel, comm_manager
    ):
        """A library-owned watcher thread keeps the comm's mode and stream."""
        from marimo._messaging.notification import (
            ModelLifecycleNotification,
            ModelUpdate,
        )
        from marimo._utils.code import hash_code

        comm = MarimoComm(
            comm_id=WidgetModelId("thread-hmr-test"),
            comm_manager=comm_manager,
            target_name="jupyter.widget",
            data={
                "state": {"_esm": "export default {}", "_css": ""},
                "buffer_paths": [],
                "method": "open",
            },
        )
        stream = executing_kernel.stream
        stream.messages.clear()
        errors: list[BaseException] = []

        def send_update() -> None:
            try:
                comm.send(
                    data={
                        "state": {
                            "_esm": self.ESM_V2,
                            "_css": "button { color: hotpink; }",
                        },
                        "buffer_paths": [],
                        "method": "update",
                    }
                )
            except BaseException as exc:
                errors.append(exc)

        watcher = threading.Thread(target=send_update)
        watcher.start()
        watcher.join(timeout=1)

        assert not watcher.is_alive()
        assert not errors
        assert len(stream.operations) == 1
        notification = stream.operations[0]
        assert isinstance(notification, ModelLifecycleNotification)
        assert isinstance(notification.message, ModelUpdate)
        assert notification.message.state == {
            "_css": "button { color: hotpink; }"
        }
        assert notification.message.esm_spec is not None
        assert notification.message.esm_spec.hash == hash_code(self.ESM_V2)
        # The callback thread intentionally does not inherit the mutable
        # runtime context; inline HMR modules therefore use the supported
        # data-URL transport instead of touching the virtual-file registry.
        assert notification.message.esm_spec.url.startswith("data:")
        comm.close()


class TestClientUpdateStrip:
    """Clients may write widget state, never widget code or style."""

    def test_strips_esm_and_css_from_client_updates(
        self, comm_manager, comm: MarimoComm
    ):
        received: list[dict] = []
        comm.on_msg(received.append)
        comm.ui_element_id = "el-1"

        command = ModelCommand(
            model_id=comm.comm_id,
            message=ModelUpdateMessage(
                state={
                    "_esm": "alert('pwned')",
                    "_css": "body { display: none }",
                    "count": 2,
                },
                buffer_paths=[],
            ),
            buffers=[],
        )
        ui_element_id, state = comm_manager.receive_comm_message(command)

        assert ui_element_id == "el-1"
        assert state == {"count": 2}
        # The comm callback (ipywidgets set_state) never sees them
        # either — otherwise the kernel would echo them back to peers.
        payload_state = received[0]["content"]["data"]["state"]
        assert "_esm" not in payload_state
        assert "_css" not in payload_state
        assert payload_state["count"] == 2
