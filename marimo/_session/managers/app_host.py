# Copyright 2026 Marimo. All rights reserved.
"""QueueManager and KernelManager adapters for an AppHost.

These adapt AppHost's multiplexed ZMQ channels to the session manager
protocols (QueueManager, KernelManager).
"""

from __future__ import annotations

import queue
from typing import TYPE_CHECKING, TypeVar

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.types import KernelMessage
from marimo._runtime import commands
from marimo._session.app_host.commands import Channel
from marimo._session.model import SessionMode
from marimo._session.queue import ProcessLike, QueueType, route_control_request
from marimo._session.types import (
    KernelManager,
    QueueManager as QueueManagerProto,
)

if TYPE_CHECKING:
    import threading

    from marimo._ast.cell import CellConfig
    from marimo._config.manager import MarimoConfigReader
    from marimo._runtime.commands import AppMetadata
    from marimo._session.app_host.host import AppHost
    from marimo._types.ids import CellId_t
    from marimo._utils.typed_connection import TypedConnection

_T = TypeVar("_T")


class _AppHostPushQueue(QueueType[_T]):
    """Queue that sends commands over the multiplexed ZMQ channel.

    Satisfies QueueType protocol for the main-process side. Only put()
    is meaningful; get() raises NotImplementedError since this queue
    is write-only from the main process perspective.
    """

    def __init__(
        self, app_host: AppHost, session_id: str, channel: Channel
    ) -> None:
        self._app_host = app_host
        self._session_id = session_id
        self._channel = channel

    def put(
        self,
        item: _T,
        /,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        """Send item over the ZMQ channel; block and timeout arguments are ignored."""
        del block, timeout
        self._app_host.send_command(self._session_id, self._channel, item)

    def put_nowait(self, item: _T, /) -> None:
        """Send item over the ZMQ channel immediately."""
        self.put(item)

    def get(self, block: bool = True, timeout: float | None = None) -> _T:
        """Not implemented; this queue is write-only."""
        raise NotImplementedError("_AppHostPushQueue is write-only")

    def get_nowait(self) -> _T:
        """Not implemented; this queue is write-only."""
        raise NotImplementedError("_AppHostPushQueue is write-only")

    def empty(self) -> bool:
        """Always return True; write-only queues have no readable items."""
        return True


class AppHostQueueManager(QueueManagerProto):
    """QueueManager for multiplexed app host communication.

    Commands are sent over a shared ZMQ channel (tagged with session_id
    and channel type). Stream output arrives via a per-session queue
    filled by the AppHost stream receiver thread.
    """

    def __init__(self, app_host: AppHost, session_id: str) -> None:
        self._app_host = app_host
        self._session_id = session_id

        self.control_queue: QueueType[commands.CommandMessage] = (
            _AppHostPushQueue(app_host, session_id, Channel.CONTROL)
        )
        self.set_ui_element_queue: QueueType[commands.BatchableCommand] = (
            _AppHostPushQueue(app_host, session_id, Channel.UI_ELEMENT)
        )
        self.completion_queue: QueueType[commands.CodeCompletionCommand] = (
            _AppHostPushQueue(app_host, session_id, Channel.COMPLETION)
        )
        self.input_queue: QueueType[str] = _AppHostPushQueue(
            app_host, session_id, Channel.INPUT
        )
        self.win32_interrupt_queue: None = None

        self.stream_queue: queue.Queue[KernelMessage | None] = queue.Queue()
        app_host.register_stream(session_id, self.stream_queue)

    def put_control_request(self, request: commands.CommandMessage) -> None:
        """Route a control request to the appropriate ZMQ channel queue."""
        route_control_request(
            request,
            self.control_queue,
            self.completion_queue,
            self.set_ui_element_queue,
        )

    def put_input(self, text: str) -> None:
        """Put a stdin input string onto the input channel."""
        self.input_queue.put(text)

    def close_queues(self) -> None:
        """Unregister the stream and signal the queue distributor to stop."""
        self._app_host.unregister_stream(self._session_id)
        self.stream_queue.put(None)  # Signal QueueDistributor to stop


class _AppHostLike(ProcessLike):
    """Makes AppHost satisfy ProcessLike for kernel_task."""

    def __init__(self, app_host: AppHost, session_id: str) -> None:
        self._app_host = app_host
        self._session_id = session_id

    @property
    def pid(self) -> int | None:
        """Return the PID of the app host process."""
        return self._app_host.pid

    def is_alive(self) -> bool:
        """Return True if the session is still active in the app host."""
        return self._app_host.has_active_session(self._session_id)

    def terminate(self) -> None:
        """No-op; kernel threads inside the app host cannot be forcibly terminated."""
        # We can't forcibly terminate a kernel thread
        pass

    def join(self, timeout: float | None = None) -> None:
        """No-op; kernel threads are cleaned up independently."""
        # We never join kernel threads, just let them get cleaned up
        # on their own
        pass


class AppHostKernelManager(KernelManager):
    """Manages the kernel for a single client session inside an app host.

    Each kernel (client session) is served by a thread inside an app's
    host process.

    Has a reference to an AppHost object which starts kernel threads
    and coordinates communication from the server to kernel threads
    and back.
    """

    def __init__(
        self,
        *,
        app_host: AppHost,
        session_id: str,
        queue_manager: QueueManagerProto,
        mode: SessionMode,
        configs: dict[CellId_t, CellConfig],
        app_metadata: AppMetadata,
        config_manager: MarimoConfigReader,
        redirect_console_to_browser: bool,
    ) -> None:
        self._app_host = app_host
        self._session_id = session_id
        self.queue_manager = queue_manager
        self.mode = mode
        self._configs = configs
        self._app_metadata = app_metadata
        self._config_manager = config_manager
        self._redirect_console_to_browser = redirect_console_to_browser

        self.kernel_task: ProcessLike | threading.Thread | None = None

    def start_kernel(self) -> None:
        """Create a kernel thread in the app host for this session."""
        response = self._app_host.create_kernel(
            session_id=self._session_id,
            configs=self._configs,
            app_metadata=self._app_metadata,
            user_config=self._config_manager.get_config(hide_secrets=False),
            virtual_files_supported=True,
            redirect_console_to_browser=self._redirect_console_to_browser,
            log_level=GLOBAL_SETTINGS.LOG_LEVEL,
        )

        if not response.success:
            raise RuntimeError(
                f"Failed to create kernel in app host: {response.error}"
            )

        # The kernel thread is created in a separate process so we don't
        # have access to its underlying thread.
        self.kernel_task = _AppHostLike(self._app_host, self._session_id)

    @property
    def pid(self) -> int | None:
        """Return the PID of the app host process."""
        return self._app_host.pid

    @property
    def profile_path(self) -> str | None:
        """Return None; profiling is not supported for app host kernels."""
        return None

    def is_alive(self) -> bool:
        """Return True if the session is still active in the app host."""
        return self._app_host.has_active_session(self._session_id)

    def interrupt_kernel(self) -> None:
        """No-op; run-mode kernel threads cannot be interrupted."""
        # Run-mode threads can't be interrupted
        pass

    def close_kernel(self) -> None:
        """Close the queue and stop the kernel thread in the app host."""
        self.queue_manager.close_queues()
        self._app_host.stop_kernel(self._session_id)

    @property
    def kernel_connection(self) -> TypedConnection[KernelMessage]:
        """Not implemented; app host kernels use stream_queue instead."""
        # App host kernels use stream_queue, not kernel_connection
        raise NotImplementedError(
            "App host kernel uses stream_queue, not kernel_connection"
        )
