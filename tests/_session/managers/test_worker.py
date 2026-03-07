# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pickle

import pytest


@pytest.mark.requires("zmq")
class TestWorkerCommands:
    def test_commands_are_picklable(self) -> None:
        """All commands must be picklable for multiprocessing.Queue."""
        from marimo._ipc.types import ConnectionInfo
        from marimo._session.managers.worker_commands import (
            CreateKernelCmd,
            KernelCreatedResponse,
            KernelStoppedResponse,
            ShutdownWorkerCmd,
            StopKernelCmd,
        )

        conn_info = ConnectionInfo(
            control=1,
            ui_element=2,
            completion=3,
            win32_interrupt=None,
            input=5,
            stream=6,
        )

        commands = [
            CreateKernelCmd(
                session_id="s1",
                connection_info=conn_info,
                configs={},
                app_metadata=None,  # type: ignore[arg-type]
                user_config=None,  # type: ignore[arg-type]
                virtual_files_supported=True,
                redirect_console_to_browser=True,
                log_level=10,
            ),
            StopKernelCmd(session_id="s1"),
            ShutdownWorkerCmd(),
            KernelCreatedResponse(session_id="s1", success=True),
            KernelCreatedResponse(
                session_id="s1", success=False, error="boom"
            ),
            KernelStoppedResponse(session_id="s1"),
        ]

        for cmd in commands:
            data = pickle.dumps(cmd)
            restored = pickle.loads(data)  # noqa: S301
            assert type(restored) is type(cmd)


@pytest.mark.requires("zmq")
class TestWorkerProcessPool:
    def test_create_and_reuse_worker(self, tmp_path: object) -> None:
        """Pool creates one worker per file and reuses it."""
        from marimo._session.managers.worker import WorkerProcessPool

        pool = WorkerProcessPool()
        try:
            w1 = pool.get_or_create("/tmp/test_app1.py")
            w2 = pool.get_or_create("/tmp/test_app1.py")
            assert w1 is w2
            assert w1.is_alive()
        finally:
            pool.shutdown()

    def test_different_files_get_different_workers(self) -> None:
        """Different files get different workers."""
        from marimo._session.managers.worker import WorkerProcessPool

        pool = WorkerProcessPool()
        try:
            w1 = pool.get_or_create("/tmp/test_app1.py")
            w2 = pool.get_or_create("/tmp/test_app2.py")
            assert w1 is not w2
            assert w1.is_alive()
            assert w2.is_alive()
        finally:
            pool.shutdown()

    def test_shutdown_stops_all_workers(self) -> None:
        """Shutdown terminates all worker processes."""
        from marimo._session.managers.worker import WorkerProcessPool

        pool = WorkerProcessPool()
        w1 = pool.get_or_create("/tmp/test_app1.py")
        w2 = pool.get_or_create("/tmp/test_app2.py")

        pool.shutdown()

        assert not w1.is_alive()
        assert not w2.is_alive()


@pytest.mark.requires("zmq")
class TestWorkerProcess:
    def test_start_and_shutdown(self) -> None:
        """Worker process starts and shuts down cleanly."""
        from marimo._session.managers.worker import WorkerProcess

        worker = WorkerProcess("/tmp/test_app.py")
        worker.start()
        assert worker.is_alive()
        assert worker.pid is not None

        worker.shutdown()
        assert not worker.is_alive()


@pytest.mark.requires("zmq")
class TestWorkerKernelManager:
    def test_satisfies_kernel_manager_protocol(self) -> None:
        """WorkerKernelManager has all required KernelManager attributes."""
        from unittest.mock import MagicMock

        from marimo._session.managers.worker import (
            WorkerKernelManager,
            WorkerProcessPool,
        )
        from marimo._session.model import SessionMode

        pool = WorkerProcessPool()
        try:
            mgr = WorkerKernelManager(
                worker_pool=pool,
                file_path="/tmp/test.py",
                session_id="s1",
                connection_info=MagicMock(),
                queue_manager=MagicMock(),
                mode=SessionMode.RUN,
                configs={},
                app_metadata=MagicMock(),
                config_manager=MagicMock(),
                redirect_console_to_browser=True,
            )

            # Check protocol attributes exist
            assert mgr.kernel_task is None
            assert mgr.mode == SessionMode.RUN
            assert mgr.pid is None
            assert mgr.profile_path is None
            assert not mgr.is_alive()

            # interrupt_kernel is a no-op
            mgr.interrupt_kernel()

            # kernel_connection raises
            with pytest.raises(NotImplementedError):
                _ = mgr.kernel_connection
        finally:
            pool.shutdown()
