# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest


@pytest.mark.requires("zmq")
class TestAppProcessCommands:
    def test_commands_roundtrip_json(self) -> None:
        """All commands must survive JSON encode/decode."""
        from marimo._config.config import DEFAULT_CONFIG
        from marimo._runtime.commands import AppMetadata
        from marimo._session.managers.app_process_commands import (
            CreateKernelCmd,
            KernelCreatedResponse,
            KernelStoppedResponse,
            ShutdownAppProcessCmd,
            StopKernelCmd,
            decode_command,
            decode_response,
            encode_command,
            encode_response,
        )

        app_metadata = AppMetadata(
            query_params={},
            cli_args={},
            app_config={},  # type: ignore[arg-type]
        )
        user_config = DEFAULT_CONFIG

        # Test commands
        commands = [
            CreateKernelCmd(
                session_id="s1",
                configs={},
                app_metadata=app_metadata,
                user_config=user_config,
                virtual_files_supported=True,
                redirect_console_to_browser=True,
                log_level=10,
            ),
            StopKernelCmd(session_id="s1"),
            ShutdownAppProcessCmd(),
        ]

        for cmd in commands:
            data = encode_command(cmd)
            restored = decode_command(data)
            assert type(restored) is type(cmd)

        # Test responses
        responses = [
            KernelCreatedResponse(session_id="s1", success=True),
            KernelCreatedResponse(
                session_id="s1", success=False, error="boom"
            ),
            KernelStoppedResponse(session_id="s1"),
        ]

        for resp in responses:
            data = encode_response(resp)
            restored = decode_response(data)
            assert type(restored) is type(resp)


@pytest.mark.requires("zmq")
class TestAppProcessPool:
    def test_create_and_reuse(self) -> None:
        """Pool creates one process per file and reuses it."""
        from marimo._session.managers.app_process import AppProcessPool

        pool = AppProcessPool()
        try:
            w1 = pool.get_or_create("/tmp/test_app1.py")
            w2 = pool.get_or_create("/tmp/test_app1.py")
            assert w1 is w2
            assert w1.is_alive()
        finally:
            pool.shutdown()

    def test_different_files_get_different_processes(self) -> None:
        """Different files get different app processes."""
        from marimo._session.managers.app_process import AppProcessPool

        pool = AppProcessPool()
        try:
            w1 = pool.get_or_create("/tmp/test_app1.py")
            w2 = pool.get_or_create("/tmp/test_app2.py")
            assert w1 is not w2
            assert w1.is_alive()
            assert w2.is_alive()
        finally:
            pool.shutdown()

    def test_shutdown_stops_all(self) -> None:
        """Shutdown terminates all app processes."""
        from marimo._session.managers.app_process import AppProcessPool

        pool = AppProcessPool()
        w1 = pool.get_or_create("/tmp/test_app1.py")
        w2 = pool.get_or_create("/tmp/test_app2.py")

        pool.shutdown()

        assert not w1.is_alive()
        assert not w2.is_alive()


@pytest.mark.requires("zmq")
class TestAppProcess:
    def test_start_and_shutdown(self) -> None:
        """App process starts and shuts down cleanly."""
        from marimo._session.managers.app_process import AppProcess

        app_proc = AppProcess("/tmp/test_app.py")
        app_proc.start()
        assert app_proc.is_alive()
        assert app_proc.pid is not None

        app_proc.shutdown()
        assert not app_proc.is_alive()


@pytest.mark.requires("zmq")
class TestMuxQueueManager:
    def test_stream_queue_is_regular_queue(self) -> None:
        """MuxQueueManager's stream_queue is a regular queue.Queue."""
        import queue

        from marimo._session.managers.app_process import (
            AppProcessPool,
            MuxQueueManager,
        )

        pool = AppProcessPool()
        try:
            app_proc = pool.get_or_create("/tmp/test_app.py")
            qm = MuxQueueManager(app_proc, "s1")
            assert isinstance(qm.stream_queue, queue.Queue)
            assert qm.win32_interrupt_queue is None

            # close_queues puts None sentinel for QueueDistributor
            qm.close_queues()
            assert qm.stream_queue.get_nowait() is None
        finally:
            pool.shutdown()


@pytest.mark.requires("zmq")
class TestAppKernelManager:
    def test_satisfies_kernel_manager_protocol(self) -> None:
        """AppKernelManager has all required KernelManager attributes."""
        from unittest.mock import MagicMock

        from marimo._session.managers.app_process import (
            AppKernelManager,
            AppProcessPool,
            MuxQueueManager,
        )
        from marimo._session.model import SessionMode

        pool = AppProcessPool()
        try:
            app_proc = pool.get_or_create("/tmp/test.py")
            qm = MuxQueueManager(app_proc, "s1")
            mgr = AppKernelManager(
                app_process=app_proc,
                session_id="s1",
                queue_manager=qm,
                mode=SessionMode.RUN,
                configs={},
                app_metadata=MagicMock(),
                config_manager=MagicMock(),
                redirect_console_to_browser=True,
            )

            # Check protocol attributes exist
            assert mgr.kernel_task is None
            assert mgr.mode == SessionMode.RUN
            assert mgr.pid is not None  # app process is running
            assert mgr.profile_path is None
            assert mgr.is_alive()  # app process is alive

            # interrupt_kernel is a no-op
            mgr.interrupt_kernel()

            # kernel_connection raises
            with pytest.raises(NotImplementedError):
                _ = mgr.kernel_connection
        finally:
            pool.shutdown()
