import multiprocessing as mp
import os
import signal
import sys
import time
from unittest.mock import patch

import pytest

from marimo._config.manager import get_default_config_manager
from marimo._messaging.ops import Interrupted, MessageOperation
from marimo._messaging.types import KernelMessage
from marimo._runtime.control_flow import MarimoInterrupt
from marimo._runtime.requests import AppMetadata, ExecuteMultipleRequest
from marimo._server.file_manager import AppFileManager
from marimo._server.ids import ConsumerId
from marimo._server.model import ConnectionState
from marimo._server.sessions import QueueManager, Session, SessionMode, SessionConsumer
from typing import Callable


class MockSessionConsumer(SessionConsumer):
    def __init__(self) -> None:
        super().__init__(ConsumerId("test-consumer"))

    def on_start(self) -> Callable[[KernelMessage], None]:
        return lambda _: None

    def on_stop(self) -> None:
        pass

    def connection_state(self) -> ConnectionState:
        return ConnectionState.OPEN

    def write_operation(self, op: MessageOperation) -> None:
        pass


def wait_for_condition(condition_func, timeout=5, interval=0.1):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(interval)
    return False


def test_double_interrupt_raises_keyboard_interrupt(monkeypatch):
    """Test that second interrupt raises KeyboardInterrupt if program didn't stop"""
    queue_manager = QueueManager(use_multiprocessing=True)
    app_metadata = AppMetadata(
        filename=None,
        query_params={},
        cli_args={},
    )
    app_file_manager = AppFileManager(None)

    session = Session.create(
        initialization_id="test",
        session_consumer=MockSessionConsumer(),
        mode=SessionMode.EDIT,
        app_metadata=app_metadata,
        app_file_manager=app_file_manager,
        user_config_manager=get_default_config_manager(current_path=None),
        virtual_files_supported=True,
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )

    try:

        def mock_broadcast():
            pass

        monkeypatch.setattr(Interrupted, "broadcast", mock_broadcast)

        session.kernel_manager.start_kernel()
        assert session.kernel_manager.is_alive()

        code = """
import time
try:
    while True:
        time.sleep(0.01)
except KeyboardInterrupt:
    time.sleep(0.01)
    """
        session.put_control_request(
            ExecuteMultipleRequest(
                cell_ids=["test"],
                codes=[code],
                request=None,
            ),
            from_consumer_id=None,
        )
        time.sleep(0.1)

        session.kernel_manager.interrupt_kernel()
        assert wait_for_condition(session.kernel_manager.is_alive), (
            "Kernel should survive first interrupt"
        )

        session.kernel_manager.interrupt_kernel()
        assert wait_for_condition(
            lambda: not session.kernel_manager.is_alive()
        ), "Kernel should be terminated after second interrupt"

    finally:
        if session.kernel_manager.is_alive():
            session.kernel_manager.close_kernel()
        queue_manager.close_queues()
        session.close()


@pytest.mark.skipif(
    not hasattr(mp, "get_all_start_methods")
    or "spawn" not in mp.get_all_start_methods()
    or sys.platform != "win32",
    reason="test requires Windows and spawn start method",
)
def test_double_interrupt_windows(monkeypatch):
    """Test double interrupt behavior on Windows"""
    queue_manager = QueueManager(use_multiprocessing=True)
    app_metadata = AppMetadata(
        filename=None,
        query_params={},
        cli_args={},
    )
    app_file_manager = AppFileManager(None)

    session = Session.create(
        initialization_id="test",
        session_consumer=MockSessionConsumer(),
        mode=SessionMode.EDIT,
        app_metadata=app_metadata,
        app_file_manager=app_file_manager,
        user_config_manager=get_default_config_manager(current_path=None),
        virtual_files_supported=True,
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )

    try:

        def mock_broadcast():
            pass

        monkeypatch.setattr(Interrupted, "broadcast", mock_broadcast)

        with patch("sys.platform", "win32"):
            session.kernel_manager.start_kernel()
            assert session.kernel_manager.is_alive()

            code = """
import time
try:
    while True:
        time.sleep(0.01)
except KeyboardInterrupt:
    time.sleep(0.01)
    """
            session.put_control_request(
                ExecuteMultipleRequest(
                    cell_ids=["test"],
                    codes=[code],
                    request=None,
                ),
                from_consumer_id=None,
            )
            time.sleep(0.1)

            session.kernel_manager.interrupt_kernel()
            assert wait_for_condition(session.kernel_manager.is_alive), (
                "Kernel should survive first interrupt"
            )

            session.kernel_manager.interrupt_kernel()
            assert wait_for_condition(
                lambda: not session.kernel_manager.is_alive()
            ), "Kernel should be terminated after second interrupt"

    finally:
        if session.kernel_manager.is_alive():
            session.kernel_manager.close_kernel()
        queue_manager.close_queues()
        session.close()
