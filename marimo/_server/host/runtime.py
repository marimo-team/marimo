# Copyright 2026 Marimo. All rights reserved.
"""The session manager as the kernel runtime behind a host.

Kernel work the host asks for is carried out through the session
manager, and what the manager sees is reported back as observations.
Sessions a browser started are published too. A runtime's id is its
session's stable id, so a restart keeps it.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._host.model import Attachment, Failed
from marimo._host.transitions import (
    Action,
    Attach,
    Conflict,
    Detach,
    KernelExited,
    KernelReady,
    StartKernel,
    StartRuntime,
    StartupProgress,
    StopKernel,
    StopRuntime,
)
from marimo._messaging.notification import StartupProgressNotification
from marimo._messaging.serde import (
    deserialize_kernel_message,
    deserialize_kernel_notification_name,
)
from marimo._session.consumer import SessionConsumer
from marimo._session.events import SessionEventListener
from marimo._session.model import ConnectionState
from marimo._types.ids import (
    AttachmentId,
    ConsumerId,
    NotebookId,
    RuntimeId,
    StableSessionId,
)
from marimo._utils.ids import new_id
from marimo._version import __version__

if TYPE_CHECKING:
    from marimo._host.host import Host
    from marimo._messaging.types import KernelMessage
    from marimo._server.host.index import WorkspaceIndex
    from marimo._server.session_manager import SessionManager
    from marimo._session.events import SessionEventBus
    from marimo._session.types import KernelExitInfo, Session

LOGGER = _loggers.marimo_logger()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class _Launch:
    """One kernel the host asked for, from the request until it is gone."""

    notebook_id: NotebookId
    runtime_id: RuntimeId
    generation: int
    session: Session | None = None
    """Set once the manager has a session for this launch."""
    stop_requested: bool = False
    """A stop arrived before the session existed; stop it on arrival."""
    closing: bool = False
    """The host asked for the close, so the manager's event is not news."""
    attachments: dict[ConsumerId, AttachmentId] = field(default_factory=dict)
    """The attachment minted for each consumer currently connected."""
    listener: _SessionListener | None = None
    """Relays the session's events while the launch is bound to one."""


class SessionManagerRuntime(SessionEventListener):
    """Runs kernels for a host with a session manager.

    Build the host with it, then call `bind`.
    """

    def __init__(self, manager: SessionManager) -> None:
        self._manager = manager
        self._host: Host | None = None
        self._index: WorkspaceIndex | None = None
        self._launches: dict[tuple[RuntimeId, int], _Launch] = {}

    def bind(self, host: Host, *, index: WorkspaceIndex | None = None) -> None:
        """Starts mirroring the manager's sessions into `host`.

        With an `index`, a session on an unlisted file is admitted to the
        project; without one it is not published.
        """
        self._host = host
        self._index = index
        self._manager.event_bus.subscribe(self)
        for session in list(self._manager.sessions.values()):
            self._adopt(session)

    @property
    def sandbox(self) -> bool:
        """Whether this server runs every kernel in a sandbox."""
        return bool(self._manager.sandbox)

    def session_for(self, runtime_id: RuntimeId) -> Session | None:
        """Returns the session running a runtime's current kernel, if any."""
        for launch in self._launches.values():
            if launch.runtime_id == runtime_id and launch.session is not None:
                return launch.session
        return None

    def _launch_for(self, session: Session) -> _Launch | None:
        for launch in self._launches.values():
            if launch.session is session:
                return launch
        return None

    async def rename(self, runtime_id: RuntimeId, path: str) -> str | None:
        """Moves a live runtime's file, returning an error message if it could not."""
        session = self.session_for(runtime_id)
        if session is None:
            return "The runtime has no running kernel"
        routing_id = self._manager.get_session_id(session)
        if routing_id is None:
            return "The runtime is not registered"
        ok, error = await self._manager.rename_session(routing_id, path)
        return None if ok else (error or "The notebook could not be moved")

    # KernelRuntime

    def perform(self, action: Action) -> None:
        if isinstance(action, StartKernel):
            key = (action.runtime_id, action.generation)
            self._launches[key] = _Launch(
                action.notebook_id, action.runtime_id, action.generation
            )
            asyncio.get_running_loop().create_task(
                self._start(action), name=f"host.start.{action.runtime_id}"
            )
        elif isinstance(action, StopKernel):
            launch = self._launches.get((action.runtime_id, action.generation))
            if launch is None:
                return
            if launch.session is None:
                launch.stop_requested = True
                return
            self._close(launch)

    async def _start(self, action: StartKernel) -> None:
        # `action.sandbox` is informational here: the manager decides for
        # the whole server, and the host reports the manager's setting.
        host = self._require_host()
        key = (action.runtime_id, action.generation)
        file = self._file_for(action.notebook_id)
        if file is None:
            self._launches.pop(key, None)
            host.observe(
                KernelExited(
                    action.runtime_id,
                    action.generation,
                    "The notebook has no file to run",
                )
            )
            return

        progress = _Progress(host, action.runtime_id, action.generation)
        try:
            session = await self._manager.start_session(
                file,
                stable_id=StableSessionId(action.runtime_id),
                observer=progress,
            )
        except Exception as e:
            LOGGER.debug("Kernel for %s failed to start", action.runtime_id)
            self._launches.pop(key, None)
            host.observe(
                KernelExited(action.runtime_id, action.generation, str(e))
            )
            return

        launch = self._launches.get(key)
        if launch is None:
            # Forgotten while starting; nothing is waiting for this kernel.
            return
        self._bind(launch, session)
        if launch.stop_requested:
            self._close(launch)
            return
        host.observe(
            KernelReady(action.runtime_id, action.generation, __version__)
        )

    def _bind(self, launch: _Launch, session: Session) -> None:
        """Ties a launch to its session and starts relaying its events."""
        launch.session = session
        launch.listener = _SessionListener(self, launch)
        session.event_bus.subscribe(launch.listener)
        # Consumers that connected before we were listening.
        for state in list(session.room.consumers.values()):
            self._attach(launch, state.consumer)

    def _close(self, launch: _Launch) -> None:
        """Closes a launch's session at the host's request."""
        host = self._require_host()
        assert launch.session is not None
        launch.closing = True
        routing_id = self._manager.get_session_id(launch.session)
        if routing_id is not None:
            self._manager.close_session(routing_id)
        else:
            launch.session.close()
        self._detach_all(launch)
        self._forget(launch)
        host.observe(
            KernelExited(launch.runtime_id, launch.generation, "Stopped")
        )

    def _forget(self, launch: _Launch) -> None:
        self._launches.pop((launch.runtime_id, launch.generation), None)
        if launch.session is not None and launch.listener is not None:
            launch.session.event_bus.unsubscribe(launch.listener)
            launch.listener = None

    # Consumers

    def _attach(self, launch: _Launch, consumer: SessionConsumer) -> None:
        host = self._require_host()
        if consumer.consumer_id in launch.attachments:
            return
        # Every consumer the manager knows is a browser tab; clients of
        # the host API attach themselves through the API.
        attachment = Attachment(
            AttachmentId(new_id("att")), "browser", None, _utcnow()
        )
        try:
            host.command(Attach(launch.notebook_id, attachment))
        except Conflict:
            return
        launch.attachments[consumer.consumer_id] = attachment.id

    def _detach(self, launch: _Launch, consumer: SessionConsumer) -> None:
        attachment_id = launch.attachments.pop(consumer.consumer_id, None)
        if attachment_id is not None:
            self._require_host().observe(
                Detach(launch.notebook_id, attachment_id)
            )

    def _detach_all(self, launch: _Launch) -> None:
        """The kernel's consumers go with it; the host hears so first."""
        host = self._require_host()
        for attachment_id in list(launch.attachments.values()):
            host.observe(Detach(launch.notebook_id, attachment_id))
        launch.attachments.clear()

    def _kernel_exited(self, launch: _Launch, info: KernelExitInfo) -> None:
        host = self._require_host()
        self._detach_all(launch)
        self._forget(launch)
        host.observe(
            KernelExited(launch.runtime_id, launch.generation, info.message)
        )

    # Sessions the manager started on its own

    async def on_session_created(self, session: Session) -> None:
        self._adopt(session)

    async def on_session_notebook_renamed(
        self, session: Session, old_path: str | None
    ) -> None:
        del old_path
        launch = self._launch_for(session)
        if launch is None:
            # An untitled notebook has just been saved: publish it now.
            self._adopt(session)
            return
        path = session.app_file_manager.path
        if path is not None and self._index is not None:
            self._index.moved(launch.notebook_id, Path(path), request_id=None)

    async def on_session_closed(self, session: Session) -> None:
        launch = self._launch_for(session)
        if launch is None or launch.closing:
            return
        self._detach_all(launch)
        self._forget(launch)
        self._require_host().observe(
            KernelExited(
                launch.runtime_id, launch.generation, "The session was closed"
            )
        )

    def _adopt(self, session: Session) -> None:
        """Publishes a session the host did not start.

        A runtime whose kernel died earlier gives way to it.
        """
        host = self._require_host()
        if self._launch_for(session) is not None:
            return
        path = session.app_file_manager.path
        notebook_id = self._notebook_for(path)
        if (
            notebook_id is None
            and path is not None
            and self._index is not None
        ):
            notebook_id = self._index.ensure(path)
        if notebook_id is None:
            LOGGER.debug(
                "Not publishing session for %s: not a known notebook",
                session.app_file_manager.path,
            )
            return
        current = host.state.notebooks[notebook_id].runtime
        if current is not None and isinstance(current.lifecycle, Failed):
            host.command(StopRuntime(notebook_id))
        host.command(
            StartRuntime(
                notebook_id,
                RuntimeId(session.stable_id),
                _utcnow(),
                sandbox=self.sandbox,
            )
        )

    # Lookups

    def _require_host(self) -> Host:
        assert self._host is not None, "bind() the runtime to a host first"
        return self._host

    def _file_for(self, notebook_id: NotebookId) -> str | None:
        state = self._require_host().state
        notebook = state.notebooks.get(notebook_id)
        if notebook is None or notebook.path is None:
            return None
        project = state.projects.get(notebook.project_id)
        if project is None or project.root is None:
            return None
        return str(project.root / notebook.path)

    def _notebook_for(self, path: str | None) -> NotebookId | None:
        if path is None:
            return None
        target = Path(path).resolve()
        state = self._require_host().state
        for notebook in state.notebooks.values():
            if notebook.path is None:
                continue
            project = state.projects.get(notebook.project_id)
            if project is None or project.root is None:
                continue
            if (project.root / notebook.path).resolve() == target:
                return notebook.id
        return None


class _SessionListener(SessionEventListener):
    """Relays one session's events to the runtime, for one launch."""

    def __init__(self, runtime: SessionManagerRuntime, launch: _Launch):
        self._runtime = runtime
        self._launch = launch

    def on_consumer_connected(
        self, session: Session, consumer: SessionConsumer
    ) -> None:
        del session
        self._runtime._attach(self._launch, consumer)

    def on_consumer_disconnected(
        self, session: Session, consumer: SessionConsumer
    ) -> None:
        del session
        self._runtime._detach(self._launch, consumer)

    def on_kernel_exited(
        self, session: Session, exit_info: KernelExitInfo
    ) -> None:
        del session
        self._runtime._kernel_exited(self._launch, exit_info)


_PHASES = {
    "preparing-environment": "Preparing the environment",
    "starting-kernel": "Starting the kernel",
}


class _Progress(SessionConsumer):
    """Watches a launch's startup and reports its phase to the host."""

    def __init__(
        self, host: Host, runtime_id: RuntimeId, generation: int
    ) -> None:
        self._host = host
        self._runtime_id = runtime_id
        self._generation = generation
        self._id = ConsumerId(f"host-progress-{runtime_id}-{generation}")

    @property
    def consumer_id(self) -> ConsumerId:
        return self._id

    def notify(self, notification: KernelMessage) -> None:
        if (
            deserialize_kernel_notification_name(notification)
            != StartupProgressNotification.name
        ):
            return
        message = deserialize_kernel_message(notification)
        assert isinstance(message, StartupProgressNotification)
        self._host.observe(
            StartupProgress(
                self._runtime_id,
                self._generation,
                _PHASES.get(message.phase, message.phase),
            )
        )

    def connection_state(self) -> ConnectionState:
        return ConnectionState.OPEN

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del session, event_bus

    def on_detach(self) -> None:
        pass
