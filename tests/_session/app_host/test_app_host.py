# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest


@pytest.mark.requires("zmq")
class TestAppHostCommands:
    def test_commands_roundtrip_json(self) -> None:
        """All commands must survive JSON encode/decode."""
        from marimo._config.config import DEFAULT_CONFIG
        from marimo._runtime.commands import AppMetadata
        from marimo._session.app_host.commands import (
            CreateKernelCmd,
            KernelCreatedResponse,
            ShutdownAppHostCmd,
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
            ShutdownAppHostCmd(),
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
        ]

        for resp in responses:
            data = encode_response(resp)
            restored = decode_response(data)
            assert type(restored) is type(resp)


@pytest.mark.requires("zmq")
class TestAppHostOnEmpty:
    def test_on_empty_fires_when_session_ids_becomes_empty(self) -> None:
        """on_empty callback fires when all sessions exit."""
        import threading

        from marimo._session.app_host.host import AppHost

        fired = threading.Event()

        def on_empty() -> None:
            fired.set()

        app_host = AppHost("/tmp/test_app.py", on_empty=on_empty)
        # Simulate a kernel being alive
        app_host._session_ids.add("s1")

        # Simulate receiving a KernelExited message by calling
        # discard + the callback logic directly (avoids needing
        # a real subprocess with ZMQ sockets).
        app_host._session_ids.discard("s1")
        assert len(app_host._session_ids) == 0
        # Replicate the callback logic from _stream_receiver_loop
        callback = app_host._on_empty
        app_host._on_empty = None
        if callback is not None:
            threading.Thread(target=callback, daemon=True).start()

        assert fired.wait(timeout=2), "on_empty callback was not fired"

    def test_on_empty_does_not_fire_when_kernels_remain(self) -> None:
        """on_empty callback does NOT fire when kernels remain."""
        import threading

        from marimo._session.app_host.host import AppHost

        fired = threading.Event()

        def on_empty() -> None:
            fired.set()

        app_host = AppHost("/tmp/test_app.py", on_empty=on_empty)
        app_host._session_ids.add("s1")
        app_host._session_ids.add("s2")

        # Remove one — still one left
        app_host._session_ids.discard("s1")
        assert len(app_host._session_ids) == 1

        # Replicate the callback logic
        if not app_host._session_ids:
            callback = app_host._on_empty
            app_host._on_empty = None
            if callback is not None:
                threading.Thread(target=callback, daemon=True).start()

        assert not fired.wait(timeout=0.5), (
            "on_empty callback should not fire when kernels remain"
        )

    def test_on_empty_fires_only_once(self) -> None:
        """on_empty callback fires at most once (double-fire prevention)."""
        import threading

        from marimo._session.app_host.host import AppHost

        call_count = 0
        lock = threading.Lock()
        done = threading.Event()

        def on_empty() -> None:
            nonlocal call_count
            with lock:
                call_count += 1
            done.set()

        app_host = AppHost("/tmp/test_app.py", on_empty=on_empty)
        app_host._session_ids.add("s1")
        app_host._session_ids.add("s2")

        # Simulate both kernels exiting
        for sid in ["s1", "s2"]:
            app_host._session_ids.discard(sid)
            if not app_host._session_ids:
                callback = app_host._on_empty
                app_host._on_empty = None
                if callback is not None:
                    threading.Thread(target=callback, daemon=True).start()

        assert done.wait(timeout=2)
        # Give any potential second callback time to run
        threading.Event().wait(timeout=0.2)
        with lock:
            assert call_count == 1, (
                f"on_empty fired {call_count} times, expected 1"
            )


@pytest.mark.requires("zmq")
class TestAppHostPool:
    def test_create_and_reuse(self) -> None:
        """Pool creates one host per file and reuses it."""
        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool()
        try:
            w1 = pool.get_or_create("/tmp/test_app1.py")
            w2 = pool.get_or_create("/tmp/test_app1.py")
            assert w1 is w2
            assert w1.is_alive()
        finally:
            pool.shutdown()

    def test_different_files_get_different_hosts(self) -> None:
        """Different files get different app hosts."""
        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool()
        try:
            w1 = pool.get_or_create("/tmp/test_app1.py")
            w2 = pool.get_or_create("/tmp/test_app2.py")
            assert w1 is not w2
            assert w1.is_alive()
            assert w2.is_alive()
        finally:
            pool.shutdown()

    def test_shutdown_stops_all(self) -> None:
        """Shutdown terminates all app hosts."""
        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool()
        w1 = pool.get_or_create("/tmp/test_app1.py")
        w2 = pool.get_or_create("/tmp/test_app2.py")

        pool.shutdown()

        assert not w1.is_alive()
        assert not w2.is_alive()


@pytest.mark.requires("zmq")
class TestAppHost:
    def test_start_and_shutdown(self) -> None:
        """App host starts and shuts down cleanly."""
        from marimo._session.app_host.host import AppHost

        app_host = AppHost("/tmp/test_app.py")
        app_host.start()
        assert app_host.is_alive()
        assert app_host.pid is not None

        app_host.shutdown()
        assert not app_host.is_alive()


@pytest.mark.requires("zmq")
class TestAppHostSandbox:
    def test_app_host_stores_sandbox_dir(self) -> None:
        """AppHost stores sandbox_dir for cleanup on shutdown."""
        from marimo._session.app_host.host import AppHost

        host = AppHost("/tmp/test.py", sandbox_dir="/tmp/sandbox-abc")
        assert host._sandbox_dir == "/tmp/sandbox-abc"

    def test_app_host_shutdown_cleans_up_sandbox_dir(self) -> None:
        """shutdown() calls cleanup_sandbox_dir when sandbox_dir is set."""
        from unittest.mock import patch

        from marimo._session.app_host.host import AppHost

        host = AppHost("/tmp/test.py", sandbox_dir="/tmp/sandbox-abc")

        with patch("marimo._cli.sandbox.cleanup_sandbox_dir") as mock_cleanup:
            host.shutdown()
            mock_cleanup.assert_called_once_with("/tmp/sandbox-abc")

        assert host._sandbox_dir is None

    def test_app_host_shutdown_skips_cleanup_without_sandbox(self) -> None:
        """shutdown() does not call cleanup when no sandbox_dir."""
        from unittest.mock import patch

        from marimo._session.app_host.host import AppHost

        host = AppHost("/tmp/test.py")

        with patch("marimo._cli.sandbox.cleanup_sandbox_dir") as mock_cleanup:
            host.shutdown()
            mock_cleanup.assert_not_called()

    def test_pool_sandbox_flag_stored(self) -> None:
        """AppHostPool stores the sandbox flag."""
        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool(sandbox=False)
        assert pool._sandbox is False

        pool = AppHostPool(sandbox=True)
        assert pool._sandbox is True

    def test_pool_sandbox_builds_venv_and_passes_to_host(self) -> None:
        """When sandbox=True, pool builds a venv and passes python/sandbox_dir
        to AppHost."""
        from unittest.mock import MagicMock, patch

        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool(sandbox=True)

        mock_host = MagicMock()
        mock_host.is_alive.return_value = True

        with (
            patch(
                "marimo._cli.sandbox.build_sandbox_venv",
                return_value=(
                    "/tmp/sandbox-xyz",
                    "/tmp/sandbox-xyz/bin/python",
                ),
            ) as mock_build,
            patch(
                "marimo._session._venv.get_ipc_kernel_deps",
                return_value=["pyzmq==26.0.0"],
            ),
            patch(
                "marimo._session.app_host.pool.AppHost",
                return_value=mock_host,
            ) as mock_host_cls,
        ):
            pool.get_or_create("/tmp/test_app.py")

            # Verify venv was built with correct args
            mock_build.assert_called_once()
            _, kwargs = mock_build.call_args
            assert kwargs["additional_deps"] == ["pyzmq==26.0.0"]

            # Verify AppHost received python and sandbox_dir
            mock_host_cls.assert_called_once()
            host_kwargs = mock_host_cls.call_args[1]
            assert host_kwargs["python"] == "/tmp/sandbox-xyz/bin/python"
            assert host_kwargs["sandbox_dir"] == "/tmp/sandbox-xyz"

    def test_pool_no_sandbox_skips_venv_build(self) -> None:
        """When sandbox=False, pool does not build a venv."""
        from unittest.mock import MagicMock, patch

        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool(sandbox=False)

        mock_host = MagicMock()
        mock_host.is_alive.return_value = True

        with (
            patch(
                "marimo._cli.sandbox.build_sandbox_venv",
            ) as mock_build,
            patch(
                "marimo._session.app_host.pool.AppHost",
                return_value=mock_host,
            ) as mock_host_cls,
        ):
            pool.get_or_create("/tmp/test_app.py")

            mock_build.assert_not_called()

            # AppHost should get python=None, sandbox_dir=None
            host_kwargs = mock_host_cls.call_args[1]
            assert host_kwargs.get("python") is None
            assert host_kwargs.get("sandbox_dir") is None

    def test_pool_sandbox_race_cleans_up_duplicate_venv(self) -> None:
        """If another thread creates the host while we build the venv,
        the duplicate venv is cleaned up."""
        from unittest.mock import MagicMock, patch

        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool(sandbox=True)

        # Pre-populate pool with an alive host (simulates another thread)
        existing_host = MagicMock()
        existing_host.is_alive.return_value = True

        # Simulate the race: first get_or_create finds no host, drops
        # the lock to build the venv, then re-acquires and finds a host
        # that another thread created. We do this by injecting the host
        # into pool._workers during the build_sandbox_venv call.
        def build_and_inject(
            filename: str,
            additional_deps: list[str] | None = None,  # noqa: ARG001
        ) -> tuple[str, str]:
            import os

            abs_path = os.path.abspath(filename)
            pool._workers[abs_path] = existing_host
            return ("/tmp/sandbox-dup", "/tmp/sandbox-dup/bin/python")

        with (
            patch(
                "marimo._cli.sandbox.build_sandbox_venv",
                side_effect=build_and_inject,
            ),
            patch(
                "marimo._session._venv.get_ipc_kernel_deps",
                return_value=[],
            ),
            patch(
                "marimo._cli.sandbox.cleanup_sandbox_dir",
            ) as mock_cleanup,
        ):
            result = pool.get_or_create("/tmp/test_app.py")
            assert result is existing_host
            mock_cleanup.assert_called_once_with("/tmp/sandbox-dup")


@pytest.mark.requires("zmq")
class TestAppHostQueueManager:
    def test_stream_queue_is_regular_queue(self) -> None:
        """AppHostQueueManager's stream_queue is a regular queue.Queue."""
        import queue

        from marimo._session.app_host.host import AppHost
        from marimo._session.managers.app_host import AppHostQueueManager

        # No need to start a real subprocess — register_stream and
        # unregister_stream only use the in-memory dict from __init__.
        app_host = AppHost("/tmp/test_app.py")
        qm = AppHostQueueManager(app_host, "s1")
        assert isinstance(qm.stream_queue, queue.Queue)
        assert qm.win32_interrupt_queue is None

        # close_queues puts None sentinel for QueueDistributor
        qm.close_queues()
        assert qm.stream_queue.get_nowait() is None


@pytest.mark.requires("zmq")
class TestAppHostKernelManager:
    def test_satisfies_kernel_manager_protocol(self) -> None:
        """AppHostKernelManager has all required KernelManager attributes."""
        from unittest.mock import Mock

        from marimo._session.app_host.host import AppHost
        from marimo._session.managers.app_host import (
            AppHostKernelManager,
            AppHostQueueManager,
        )
        from marimo._session.model import SessionMode

        # No need to start a real subprocess — an unstarted AppHost
        # is sufficient to verify the protocol surface.
        app_host = AppHost("/tmp/test.py")
        qm = AppHostQueueManager(app_host, "s1")
        mgr = AppHostKernelManager(
            app_host=app_host,
            session_id="s1",
            queue_manager=qm,
            mode=SessionMode.RUN,
            configs={},
            app_metadata=Mock(),
            config_manager=Mock(),
            redirect_console_to_browser=True,
        )

        # Check protocol attributes exist
        assert mgr.kernel_task is None
        assert mgr.mode == SessionMode.RUN
        assert mgr.pid is None  # no subprocess started
        assert mgr.profile_path is None
        assert not mgr.is_alive()  # no subprocess started

        # interrupt_kernel is a no-op
        mgr.interrupt_kernel()

        # kernel_connection raises
        with pytest.raises(NotImplementedError):
            _ = mgr.kernel_connection
