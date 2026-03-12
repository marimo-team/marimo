# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import Mock, PropertyMock

import pytest

from marimo._runtime.commands import (
    CodeCompletionCommand,
    ModelCommand,
    ModelUpdateMessage,
    StopKernelCommand,
    UpdateUIElementCommand,
)
from marimo._session.app_host.commands import KernelCreatedResponse
from marimo._session.managers.app_host import (
    AppHostKernelManager,
    AppHostQueueManager,
    _AppHostLike,
    _AppHostPushQueue,
)
from marimo._session.model import SessionMode


@pytest.mark.requires("zmq")
class TestAppHostPushQueue:
    def test_put_calls_send_command(self) -> None:
        app_host = Mock()
        q = _AppHostPushQueue(app_host, "s1", "control")
        q.put("payload")
        app_host.send_command.assert_called_once_with(
            "s1", "control", "payload"
        )

    def test_put_nowait_calls_send_command(self) -> None:
        app_host = Mock()
        q = _AppHostPushQueue(app_host, "s1", "control")
        q.put_nowait("payload")
        app_host.send_command.assert_called_once_with(
            "s1", "control", "payload"
        )

    def test_get_raises_not_implemented(self) -> None:
        q = _AppHostPushQueue(Mock(), "s1", "control")
        with pytest.raises(NotImplementedError):
            q.get()

    def test_get_nowait_raises_not_implemented(self) -> None:
        q = _AppHostPushQueue(Mock(), "s1", "control")
        with pytest.raises(NotImplementedError):
            q.get_nowait()

    def test_empty_always_returns_true(self) -> None:
        q = _AppHostPushQueue(Mock(), "s1", "control")
        assert q.empty() is True


@pytest.mark.requires("zmq")
class TestPutControlRequestRouting:
    def _make_queue_manager(self) -> AppHostQueueManager:
        app_host = Mock()
        qm = AppHostQueueManager(app_host, "s1")
        # Replace push queues with mocks so we can track calls
        qm.control_queue = Mock()
        qm.set_ui_element_queue = Mock()
        qm.completion_queue = Mock()
        qm.input_queue = Mock()
        return qm

    def test_completion_goes_to_completion_queue_only(self) -> None:
        qm = self._make_queue_manager()
        cmd = CodeCompletionCommand(id="r1", document="x.", cell_id="c1")

        qm.put_control_request(cmd)

        qm.completion_queue.put.assert_called_once_with(cmd)
        qm.control_queue.put.assert_not_called()
        qm.set_ui_element_queue.put.assert_not_called()

    def test_ui_element_goes_to_both_queues(self) -> None:
        qm = self._make_queue_manager()
        cmd = UpdateUIElementCommand(object_ids=["ui1"], values=[42])

        qm.put_control_request(cmd)

        qm.control_queue.put.assert_called_once_with(cmd)
        qm.set_ui_element_queue.put.assert_called_once_with(cmd)
        qm.completion_queue.put.assert_not_called()

    def test_model_command_goes_to_both_queues(self) -> None:
        qm = self._make_queue_manager()
        cmd = ModelCommand(
            model_id="m1",
            message=ModelUpdateMessage(state={}, buffer_paths=[]),
            buffers=[],
        )

        qm.put_control_request(cmd)

        qm.control_queue.put.assert_called_once_with(cmd)
        qm.set_ui_element_queue.put.assert_called_once_with(cmd)
        qm.completion_queue.put.assert_not_called()

    def test_regular_command_goes_to_control_queue_only(self) -> None:
        qm = self._make_queue_manager()
        cmd = StopKernelCommand()

        qm.put_control_request(cmd)

        qm.control_queue.put.assert_called_once_with(cmd)
        qm.completion_queue.put.assert_not_called()
        qm.set_ui_element_queue.put.assert_not_called()


@pytest.mark.requires("zmq")
class TestAppHostLike:
    def test_pid_delegates_to_app_host(self) -> None:
        app_host = Mock()
        type(app_host).pid = PropertyMock(return_value=1234)
        like = _AppHostLike(app_host, "s1")
        assert like.pid == 1234

    def test_is_alive_delegates_to_is_session_ids(self) -> None:
        app_host = Mock()
        app_host.is_session_ids.return_value = True
        like = _AppHostLike(app_host, "s1")
        assert like.is_alive() is True
        app_host.is_session_ids.assert_called_once_with("s1")

    def test_terminate_is_noop(self) -> None:
        like = _AppHostLike(Mock(), "s1")
        like.terminate()  # should not raise

    def test_join_is_noop(self) -> None:
        like = _AppHostLike(Mock(), "s1")
        like.join(timeout=1.0)  # should not raise


@pytest.mark.requires("zmq")
class TestAppHostKernelManagerStartAndClose:
    def test_start_kernel_sets_kernel_task(self) -> None:
        app_host = Mock()
        app_host.create_kernel.return_value = KernelCreatedResponse(
            session_id="s1", success=True
        )

        config_manager = Mock()
        config_manager.get_config.return_value = {}

        mgr = AppHostKernelManager(
            app_host=app_host,
            session_id="s1",
            queue_manager=Mock(),
            mode=SessionMode.RUN,
            configs={},
            app_metadata=Mock(),
            config_manager=config_manager,
            redirect_console_to_browser=True,
        )

        mgr.start_kernel()

        app_host.create_kernel.assert_called_once()
        assert isinstance(mgr.kernel_task, _AppHostLike)

    def test_start_kernel_failure_raises(self) -> None:
        app_host = Mock()
        app_host.create_kernel.return_value = KernelCreatedResponse(
            session_id="s1", success=False, error="boom"
        )

        config_manager = Mock()
        config_manager.get_config.return_value = {}

        mgr = AppHostKernelManager(
            app_host=app_host,
            session_id="s1",
            queue_manager=Mock(),
            mode=SessionMode.RUN,
            configs={},
            app_metadata=Mock(),
            config_manager=config_manager,
            redirect_console_to_browser=True,
        )

        with pytest.raises(RuntimeError, match="boom"):
            mgr.start_kernel()

        assert mgr.kernel_task is None

    def test_close_kernel_calls_close_queues_and_stop_kernel(self) -> None:
        app_host = Mock()
        queue_manager = Mock()

        mgr = AppHostKernelManager(
            app_host=app_host,
            session_id="s1",
            queue_manager=queue_manager,
            mode=SessionMode.RUN,
            configs={},
            app_metadata=Mock(),
            config_manager=Mock(),
            redirect_console_to_browser=True,
        )

        mgr.close_kernel()

        queue_manager.close_queues.assert_called_once()
        app_host.stop_kernel.assert_called_once_with("s1")
