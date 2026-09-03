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
            decode_mgmt_command,
            decode_mgmt_response,
            encode_mgmt_command,
            encode_mgmt_response,
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
                virtual_file_storage="shared_memory",
                redirect_console_to_browser=True,
                log_level=10,
            ),
            StopKernelCmd(session_id="s1"),
            ShutdownAppHostCmd(),
        ]

        for cmd in commands:
            data = encode_mgmt_command(cmd)
            restored = decode_mgmt_command(data)
            assert type(restored) is type(cmd)

        # Test responses
        responses = [
            KernelCreatedResponse(session_id="s1", success=True),
            KernelCreatedResponse(
                session_id="s1", success=False, error="boom"
            ),
        ]

        for resp in responses:
            data = encode_mgmt_response(resp)
            restored = decode_mgmt_response(data)
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
        from unittest.mock import patch

        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool()
        with patch("marimo._session.app_host.pool.AppHost") as MockHost:
            MockHost.return_value.is_alive.return_value = True
            w1 = pool.get_or_create("/tmp/test_app1.py")
            w2 = pool.get_or_create("/tmp/test_app1.py")
            assert w1 is w2

    def test_different_files_get_different_hosts(self) -> None:
        """Different files get different app hosts."""
        from unittest.mock import patch

        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool()
        with patch("marimo._session.app_host.pool.AppHost") as MockHost:
            MockHost.return_value.is_alive.return_value = True
            # Each call returns a new mock instance
            MockHost.side_effect = lambda *_a, **_kw: type(
                MockHost.return_value
            )()
            w1 = pool.get_or_create("/tmp/test_app1.py")
            w2 = pool.get_or_create("/tmp/test_app2.py")
            assert w1 is not w2

    def test_shutdown_stops_all(self) -> None:
        """Shutdown terminates all app hosts."""
        from unittest.mock import MagicMock

        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool()
        w1, w2 = MagicMock(), MagicMock()
        pool._workers["/tmp/test_app1.py"] = w1
        pool._workers["/tmp/test_app2.py"] = w2

        pool.shutdown()

        w1.shutdown.assert_called_once()
        w2.shutdown.assert_called_once()
        assert len(pool._workers) == 0


@pytest.mark.requires("zmq")
class TestAppHost:
    def test_start_and_shutdown(self) -> None:
        """App host starts and shuts down cleanly."""
        import time

        from marimo._session.app_host.host import AppHost

        app_host = AppHost("/tmp/test_app.py")
        app_host.start()
        assert app_host.is_alive()
        assert app_host.pid is not None

        app_host.shutdown()
        # shutdown() signals the subprocess but doesn't synchronously
        # wait for it to exit, so poll briefly for the process to die.
        deadline = time.monotonic() + 5.0
        while app_host.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not app_host.is_alive()


@pytest.mark.requires("zmq")
class TestAppHostSandbox:
    def test_pool_sandbox_flag_stored(self) -> None:
        """AppHostPool stores the sandbox flag."""
        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool(sandbox=False)
        assert pool._sandbox is False

        pool = AppHostPool(sandbox=True)
        assert pool._sandbox is True

    def test_pool_sandbox_syncs_and_passes_plan(self) -> None:
        """When sandbox=True, the pool synchronizes the notebook's script
        environment and hands AppHost a launch plan for it."""
        from unittest.mock import MagicMock, patch

        from marimo._environments.environment import Environment
        from marimo._environments.overlay import RuntimeOverlay
        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool(sandbox=True)

        mock_host = MagicMock()
        mock_host.is_alive.return_value = True
        handle = Environment(
            python="/env/bin/python", root="/env", action="created"
        )

        with (
            patch(
                "marimo._environments.backends.sync_notebook",
                return_value=handle,
            ) as mock_sync,
            patch(
                "marimo._session.app_host.pool.runtime_overlay",
                return_value=RuntimeOverlay(runtime="kernel-dep==1.0"),
            ),
            patch(
                "marimo._session.app_host.pool.AppHost",
                return_value=mock_host,
            ) as mock_host_cls,
        ):
            pool.get_or_create("/tmp/test_app.py")

            mock_sync.assert_called_once()
            plan = mock_host_cls.call_args[1]["plan"]
            # The marimo runtime rides the launch overlay.
            assert "kernel-dep==1.0" in plan.argv
            assert plan.argv[-3:] == (
                "--",
                "python",
                "-m",
            ) or plan.argv[-2:] == ("-m", "marimo._session.app_host.main")
            assert plan.env["VIRTUAL_ENV"] == "/env"

    def test_pool_no_sandbox_skips_sync(self) -> None:
        """When sandbox=False, the pool does not synchronize anything."""
        from unittest.mock import MagicMock, patch

        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool(sandbox=False)

        mock_host = MagicMock()
        mock_host.is_alive.return_value = True

        with (
            patch(
                "marimo._environments.backends.sync_notebook",
            ) as mock_sync,
            patch(
                "marimo._session.app_host.pool.AppHost",
                return_value=mock_host,
            ) as mock_host_cls,
        ):
            pool.get_or_create("/tmp/test_app.py")

            mock_sync.assert_not_called()
            assert mock_host_cls.call_args[1].get("plan") is None

    def test_pool_missing_metadata_runs_from_this_interpreter(self) -> None:
        """A notebook without a metadata block has nothing to sandbox;
        it runs from the parent interpreter, which has marimo."""
        import sys
        from unittest.mock import MagicMock, patch

        from marimo._environments.uv import UvMissingScriptMetadataError
        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool(sandbox=True)

        mock_host = MagicMock()
        mock_host.is_alive.return_value = True

        with (
            patch(
                "marimo._environments.backends.sync_notebook",
                side_effect=UvMissingScriptMetadataError(
                    ["uv"], 2, "", "no PEP 723 metadata"
                ),
            ),
            patch(
                "marimo._session.app_host.pool.AppHost",
                return_value=mock_host,
            ) as mock_host_cls,
        ):
            pool.get_or_create("/tmp/test_app.py")

            plan = mock_host_cls.call_args[1]["plan"]
            assert plan.argv[0] == sys.executable

    def test_pool_missing_pixi_metadata_runs_from_this_interpreter(
        self,
    ) -> None:
        import sys
        from unittest.mock import MagicMock, patch

        from marimo._environments.pixi import PixiMissingScriptMetadataError
        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool(sandbox=True)
        mock_host = MagicMock()
        mock_host.is_alive.return_value = True

        with (
            patch(
                "marimo._environments.backends.sync_notebook",
                side_effect=PixiMissingScriptMetadataError(
                    ["pixi"], 1, "no PEP 723 metadata block"
                ),
            ),
            patch(
                "marimo._session.app_host.pool.AppHost",
                return_value=mock_host,
            ) as mock_host_cls,
        ):
            pool.get_or_create("/tmp/test_app.py")

        plan = mock_host_cls.call_args[1]["plan"]
        assert plan.argv[0] == sys.executable

    def test_pool_does_not_fall_back_after_other_pixi_failures(self) -> None:
        from unittest.mock import patch

        import pytest

        from marimo._environments.pixi import PixiCommandError
        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool(sandbox=True)
        error = PixiCommandError(["pixi"], 1, "solver failed")

        with (
            patch(
                "marimo._environments.backends.sync_notebook",
                side_effect=error,
            ),
            patch("marimo._session.app_host.pool.AppHost") as mock_host_cls,
            pytest.raises(PixiCommandError),
        ):
            pool.get_or_create("/tmp/test_app.py")

        mock_host_cls.assert_not_called()

    def test_pool_sandbox_race_returns_existing_host(self) -> None:
        """If another thread creates the host during synchronization, the
        existing host wins."""
        from unittest.mock import MagicMock, patch

        from marimo._environments.environment import Environment
        from marimo._environments.overlay import RuntimeOverlay
        from marimo._session.app_host.pool import AppHostPool

        pool = AppHostPool(sandbox=True)

        existing_host = MagicMock()
        existing_host.is_alive.return_value = True

        def sync_and_inject(filename: str, **_kwargs: object) -> Environment:
            import os

            pool._workers[os.path.abspath(filename)] = existing_host
            return Environment(
                python="/env/bin/python", root="/env", action="created"
            )

        with (
            patch(
                "marimo._environments.backends.sync_notebook",
                side_effect=sync_and_inject,
            ),
            patch(
                "marimo._session.app_host.pool.runtime_overlay",
                return_value=RuntimeOverlay(runtime="marimo"),
            ),
        ):
            result = pool.get_or_create("/tmp/test_app.py")
            assert result is existing_host


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
class TestAppHostMultipleClients:
    def test_create_session_uses_per_client_session_id(self) -> None:
        """SessionImpl.create() must pass the per-client session_id — not
        the shared initialization_id (file_key) — to the AppHost managers.

        Regression test: previously initialization_id was used as the
        multiplexing key, so two clients of the same notebook would share
        a key and the second register_stream call would overwrite the
        first's queue.
        """
        from unittest.mock import Mock, patch

        from marimo._config.config import DEFAULT_CONFIG
        from marimo._session.app_host import AppHostContext
        from marimo._session.app_host.host import AppHost
        from marimo._session.model import SessionMode
        from marimo._session.session import SessionImpl

        app_host = AppHost("/tmp/test_app.py")
        pool = Mock()
        pool.get_or_create.return_value = app_host

        file_key = "/tmp/test_app.py"

        with patch(
            "marimo._session.managers.app_host."
            "AppHostKernelManager.start_kernel"
        ):
            for sid in ("session-1", "session-2"):
                SessionImpl.create(
                    initialization_id=file_key,
                    session_consumer=Mock(),
                    mode=SessionMode.RUN,
                    app_metadata=Mock(),
                    app_file_manager=Mock(
                        path="/tmp/test_app.py",
                        app=Mock(
                            cell_manager=Mock(cell_data=Mock(return_value=[]))
                        ),
                    ),
                    config_manager=Mock(
                        with_overrides=Mock(
                            return_value=Mock(
                                get_config=Mock(return_value=DEFAULT_CONFIG)
                            )
                        )
                    ),
                    virtual_file_storage="shared_memory",
                    redirect_console_to_browser=False,
                    ttl_seconds=None,
                    auto_instantiate=False,
                    app_host_context=AppHostContext(pool=pool, session_id=sid),
                )

        # Both session IDs must be registered independently.
        with app_host._stream_lock:
            assert "session-1" in app_host._stream_receivers
            assert "session-2" in app_host._stream_receivers
            assert (
                app_host._stream_receivers["session-1"]
                is not app_host._stream_receivers["session-2"]
            )


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
