# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pickle
import queue
from unittest.mock import Mock, patch

import pytest

from marimo._config.config import DEFAULT_CONFIG
from marimo._runtime.commands import AppMetadata, StopKernelCommand
from marimo._session.app_host.commands import (
    CHANNEL_COMPLETION,
    CHANNEL_CONTROL,
    CHANNEL_INPUT,
    CHANNEL_UI_ELEMENT,
    CreateKernelCmd,
    KernelCreatedResponse,
    StopKernelCmd,
    decode_response,
)
from marimo._session.app_host.main import (
    _KernelInfo,
    _KernelQueues,
    _TaggedStreamQueue,
    _handle_command,
    _handle_create_kernel,
    _handle_stop_kernel,
    _shutdown_all_kernels,
    _stream_collector_loop,
)


@pytest.mark.requires("zmq")
class TestTaggedStreamQueue:
    def test_put_tags_item_with_session_id(self) -> None:
        outbox: queue.Queue[object] = queue.Queue()
        tsq = _TaggedStreamQueue("s1", outbox)
        tsq.put("hello")
        assert outbox.get_nowait() == ("s1", "hello")

    def test_put_nowait_tags_item_with_session_id(self) -> None:
        outbox: queue.Queue[object] = queue.Queue()
        tsq = _TaggedStreamQueue("s1", outbox)
        tsq.put_nowait("hello")
        assert outbox.get_nowait() == ("s1", "hello")

    def test_get_raises_not_implemented(self) -> None:
        tsq = _TaggedStreamQueue("s1", queue.Queue())
        with pytest.raises(NotImplementedError):
            tsq.get()

    def test_get_nowait_raises_not_implemented(self) -> None:
        tsq = _TaggedStreamQueue("s1", queue.Queue())
        with pytest.raises(NotImplementedError):
            tsq.get_nowait()

    def test_empty_always_returns_true(self) -> None:
        outbox: queue.Queue[object] = queue.Queue()
        tsq = _TaggedStreamQueue("s1", outbox)
        tsq.put("something")
        assert tsq.empty() is True


@pytest.mark.requires("zmq")
class TestHandleCommand:
    def _make_kernel_info(
        self, session_id: str = "s1"
    ) -> tuple[_KernelInfo, _KernelQueues]:
        queues = _KernelQueues(
            control=queue.Queue(),
            ui_element=queue.Queue(),
            completion=queue.Queue(),
            input=queue.Queue(),
        )
        info = _KernelInfo(
            thread=Mock(), queues=queues, session_id=session_id
        )
        return info, queues

    def _make_cmd_socket(
        self, session_id: str, channel: str, payload: object
    ) -> Mock:
        sock = Mock()
        sock.recv_multipart.return_value = [
            session_id.encode(),
            channel.encode(),
            pickle.dumps(payload),
        ]
        return sock

    def test_routes_to_control_queue(self) -> None:
        info, queues = self._make_kernel_info()
        sock = self._make_cmd_socket("s1", CHANNEL_CONTROL, "ctrl_payload")
        _handle_command(sock, {"s1": info})
        assert queues.control.get_nowait() == "ctrl_payload"

    def test_routes_to_ui_element_queue(self) -> None:
        info, queues = self._make_kernel_info()
        sock = self._make_cmd_socket("s1", CHANNEL_UI_ELEMENT, "ui_payload")
        _handle_command(sock, {"s1": info})
        assert queues.ui_element.get_nowait() == "ui_payload"

    def test_routes_to_completion_queue(self) -> None:
        info, queues = self._make_kernel_info()
        sock = self._make_cmd_socket(
            "s1", CHANNEL_COMPLETION, "comp_payload"
        )
        _handle_command(sock, {"s1": info})
        assert queues.completion.get_nowait() == "comp_payload"

    def test_routes_to_input_queue(self) -> None:
        info, queues = self._make_kernel_info()
        sock = self._make_cmd_socket("s1", CHANNEL_INPUT, "input_payload")
        _handle_command(sock, {"s1": info})
        assert queues.input.get_nowait() == "input_payload"

    def test_drops_command_for_unknown_session(self) -> None:
        """No error when session_id is not in the registry."""
        sock = self._make_cmd_socket("unknown", CHANNEL_CONTROL, "payload")
        _handle_command(sock, {})  # empty registry

    def test_unknown_channel_does_not_enqueue(self) -> None:
        """Payload is not routed to any queue for an unknown channel."""
        info, queues = self._make_kernel_info()
        sock = self._make_cmd_socket("s1", "bogus", "payload")
        _handle_command(sock, {"s1": info})
        assert queues.control.empty()
        assert queues.ui_element.empty()
        assert queues.completion.empty()
        assert queues.input.empty()


@pytest.mark.requires("zmq")
class TestHandleStopKernel:
    def test_removes_from_registry_and_sends_stop_command(self) -> None:
        queues = _KernelQueues(
            control=queue.Queue(),
            ui_element=queue.Queue(),
            completion=queue.Queue(),
            input=queue.Queue(),
        )
        info = _KernelInfo(thread=Mock(), queues=queues, session_id="s1")
        kernels = {"s1": info}

        _handle_stop_kernel(StopKernelCmd(session_id="s1"), kernels)

        assert "s1" not in kernels
        assert isinstance(queues.control.get_nowait(), StopKernelCommand)

    def test_noop_for_unknown_session(self) -> None:
        _handle_stop_kernel(StopKernelCmd(session_id="unknown"), {})


@pytest.mark.requires("zmq")
class TestHandleCreateKernelFailure:
    def test_failure_sends_error_response(self) -> None:
        cmd = CreateKernelCmd(
            session_id="s1",
            configs={},
            app_metadata=AppMetadata(
                query_params={}, cli_args={}, app_config={}  # type: ignore[arg-type]
            ),
            user_config=DEFAULT_CONFIG,
            virtual_files_supported=True,
            redirect_console_to_browser=True,
            log_level=10,
        )
        kernels: dict[str, _KernelInfo] = {}
        outbox: queue.Queue[object] = queue.Queue()
        response_socket = Mock()

        with patch(
            "marimo._session.app_host.main.threading.Thread",
            side_effect=RuntimeError("thread failed"),
        ):
            _handle_create_kernel(cmd, kernels, outbox, response_socket)

        assert len(kernels) == 0
        response_socket.send.assert_called_once()
        resp = decode_response(response_socket.send.call_args[0][0])
        assert isinstance(resp, KernelCreatedResponse)
        assert resp.success is False
        assert resp.session_id == "s1"
        assert "thread failed" in (resp.error or "")


@pytest.mark.requires("zmq")
class TestStreamCollectorLoop:
    def test_reads_outbox_and_sends_over_socket(self) -> None:
        outbox: queue.Queue[object] = queue.Queue()
        stream_socket = Mock()

        outbox.put(("s1", "hello"))
        outbox.put(None)  # stop sentinel

        _stream_collector_loop(outbox, stream_socket)

        stream_socket.send_multipart.assert_called_once_with(
            [b"s1", pickle.dumps("hello")]
        )

    def test_stops_on_none_sentinel(self) -> None:
        outbox: queue.Queue[object] = queue.Queue()
        stream_socket = Mock()

        outbox.put(None)
        _stream_collector_loop(outbox, stream_socket)

        stream_socket.send_multipart.assert_not_called()

    def test_continues_on_send_exception(self) -> None:
        outbox: queue.Queue[object] = queue.Queue()
        stream_socket = Mock()
        stream_socket.send_multipart.side_effect = [
            RuntimeError("send failed"),
            None,
        ]

        outbox.put(("s1", "msg1"))
        outbox.put(("s2", "msg2"))
        outbox.put(None)

        _stream_collector_loop(outbox, stream_socket)

        assert stream_socket.send_multipart.call_count == 2
        stream_socket.send_multipart.assert_any_call(
            [b"s1", pickle.dumps("msg1")]
        )
        stream_socket.send_multipart.assert_any_call(
            [b"s2", pickle.dumps("msg2")]
        )


@pytest.mark.requires("zmq")
class TestShutdownAllKernels:
    def test_sends_stop_command_to_all_kernels(self) -> None:
        queues1 = _KernelQueues(
            control=queue.Queue(),
            ui_element=queue.Queue(),
            completion=queue.Queue(),
            input=queue.Queue(),
        )
        queues2 = _KernelQueues(
            control=queue.Queue(),
            ui_element=queue.Queue(),
            completion=queue.Queue(),
            input=queue.Queue(),
        )
        kernels = {
            "s1": _KernelInfo(
                thread=Mock(), queues=queues1, session_id="s1"
            ),
            "s2": _KernelInfo(
                thread=Mock(), queues=queues2, session_id="s2"
            ),
        }

        _shutdown_all_kernels(kernels)

        assert isinstance(queues1.control.get_nowait(), StopKernelCommand)
        assert isinstance(queues2.control.get_nowait(), StopKernelCommand)
        assert len(kernels) == 0

    def test_continues_on_exception_and_clears(self) -> None:
        bad_queue = Mock()
        bad_queue.put.side_effect = RuntimeError("put failed")
        queues1 = _KernelQueues(
            control=bad_queue,
            ui_element=queue.Queue(),
            completion=queue.Queue(),
            input=queue.Queue(),
        )
        queues2 = _KernelQueues(
            control=queue.Queue(),
            ui_element=queue.Queue(),
            completion=queue.Queue(),
            input=queue.Queue(),
        )
        kernels = {
            "s1": _KernelInfo(
                thread=Mock(), queues=queues1, session_id="s1"
            ),
            "s2": _KernelInfo(
                thread=Mock(), queues=queues2, session_id="s2"
            ),
        }

        _shutdown_all_kernels(kernels)

        assert isinstance(queues2.control.get_nowait(), StopKernelCommand)
        assert len(kernels) == 0
