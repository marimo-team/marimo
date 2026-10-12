# Copyright 2026 Marimo. All rights reserved.
"""Notebook runtimes, client attachments, and runs.

Runtime and run commands call a backend. `Notebook.observe` applies
backend updates and publishes events.
"""

from __future__ import annotations

from time import monotonic
from typing import TYPE_CHECKING

from msgspec.structs import replace

from marimo._core import backend as be, protocol
from marimo._core.errors import Conflict, NoRuntime, NotFound
from marimo._core.execution_state import ExecutionState, RetentionPolicy
from marimo._core.ids import mint
from marimo._core.stream import Event, kind_of, message, utcnow

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._core.stream import Stream


class Notebook:
    """A notebook's state and commands.

    Snapshots preserve insertion order for runs, executions, and items.
    Current cell results survive runtime stops and restarts. The host
    chooses how long to retain completed ephemeral results.
    Removing the notebook closes it; further commands raise `NotFound`.
    """

    def __init__(
        self,
        notebook_id: protocol.NotebookId,
        backend: be.Backend,
        stream: Stream,
        retention: RetentionPolicy | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._id = notebook_id
        self._backend = backend
        self._stream = stream
        self._closed = False
        self._runtime: protocol.Runtime | None = None
        self._attachments: dict[str, protocol.Attachment] = {}
        self._state = ExecutionState(
            notebook_id,
            stream,
            retention or RetentionPolicy(),
            clock,
            forget=backend.forget,
        )
        self._replacement: protocol.Runtime | None = None
        # Associate runtime events with the pending start, stop, or restart.
        self._lifecycle_request: str | None = None

    def expire(self) -> None:
        """Apply the host's result retention policy."""
        self._state.expire()

    @property
    def id(self) -> protocol.NotebookId:
        return self._id

    @property
    def runtime(self) -> protocol.Runtime | None:
        """The current runtime, updated by commands and backend observations."""
        return self._runtime

    def _require_open(self) -> None:
        if self._closed:
            raise NotFound(f"no notebook {self.id}")

    # ---- runtime -------------------------------------------------------

    def start(
        self, *, request_id: str | None = None
    ) -> tuple[protocol.Runtime, bool]:
        """Start a runtime if none exists.

        Returns the runtime and whether a new runtime was created.
        An existing runtime is returned unchanged, regardless of status.
        """
        self._require_open()
        if self._runtime is not None:
            return self._runtime, False
        runtime = self._new_runtime("starting", None, None)
        self._lifecycle_request = request_id
        self._set_runtime(runtime)
        self._backend.start(runtime.id)
        return runtime, True

    def stop(self, *, request_id: str | None = None) -> protocol.Runtime:
        """Stop the runtime for all attached clients, retaining its results.

        Removal waits for the backend to report that the kernel exited.
        Failed runtimes are removed immediately. Returns the runtime
        with status `terminating`.

        Raises:
            NoRuntime: If the notebook has no runtime.
        """
        self._require_open()
        runtime = self._require_runtime()
        self._lifecycle_request = request_id
        self._replacement = None
        if runtime.status == "terminating":
            return runtime
        terminating = replace(runtime, status="terminating")
        self._set_runtime(terminating)
        if runtime.status == "failed":
            self._end_runtime()
        else:
            self._backend.stop()
        return terminating

    def restart(self, *, request_id: str | None = None) -> protocol.Runtime:
        """Stop the runtime and start a replacement with a new ID.

        Returns the replacement in its starting state. The replacement
        appears on the stream after the old runtime is removed.

        Raises:
            NoRuntime: If the notebook has no runtime.
            Conflict: If the runtime is not running.
        """
        self._require_open()
        runtime = self._require_runtime()
        if runtime.status != "running":
            raise Conflict(
                f"the runtime is {runtime.status}; only a running one restarts"
            )
        self._lifecycle_request = request_id
        replacement = self._new_runtime("starting", None, None)
        self._replacement = replacement
        terminating = replace(runtime, status="terminating")
        self._set_runtime(terminating)
        self._backend.stop()
        return replacement

    def _require_runtime(self) -> protocol.Runtime:
        if self._runtime is None:
            raise NoRuntime(
                f"notebook {self.id} has no runtime; start one first."
            )
        return self._runtime

    def _set_runtime(self, runtime: protocol.Runtime) -> None:
        self._runtime = runtime
        self._publish(runtime, self._lifecycle_request)
        if runtime.status in ("running", "failed"):
            self._lifecycle_request = None

    def _end_runtime(self) -> None:
        assert self._runtime is not None
        self._state.interrupt()
        runtime, self._runtime = self._runtime, None
        self._remove("runtime", runtime.id, self._lifecycle_request)
        self._lifecycle_request = None

    # ---- runs ----------------------------------------------------------

    def run(self, code: str, *, request_id: str) -> protocol.Run:
        """Queue scratch code on the runtime.

        The request ID identifies the run. Repeating a request returns
        the existing run while it is retained.

        Raises:
            NoRuntime: If the notebook has no runtime.
            Conflict: If the runtime is not running, or a run is in progress.
        """
        self._require_open()
        run = self._state.request_run(request_id)
        if run is not None:
            return run
        runtime = self._require_runtime()
        if runtime.status != "running":
            raise Conflict(f"the runtime is {runtime.status}.")
        if (active := self._state.active_run) is not None:
            raise Conflict(f"run {active.id} is in progress.")
        run = protocol.Run(
            id=protocol.RunId(request_id),
            notebook_id=self.id,
            caused_by=None,
            status="queued",
            outcome=None,
            started_at=None,
            completed_at=None,
        )
        self._state.add_run(run, request_id)
        self._backend.run(run.id, code)
        return run

    def interrupt(self, run_id: str) -> protocol.Run:
        """Request interruption of a run in progress.

        Raises:
            NotFound: If there is no such run.
            Conflict: If the run is already completed.
        """
        self._require_open()
        run = self._state.run(run_id)
        if run is None:
            raise NotFound(f"notebook {self.id} has no run {run_id}.")
        if run.status == "completed":
            raise Conflict(f"run {run_id} has already ended.")
        self._backend.interrupt(run.id)
        return run

    # ---- attachments ---------------------------------------------------

    def attach(self) -> protocol.Attachment:
        """Record an attached host API client."""
        self._require_open()
        attachment = protocol.Attachment(
            id=mint(protocol.AttachmentId, "att"),
            notebook_id=self.id,
            kind="client",
            name=None,
            since=utcnow(),
        )
        self._attachments[attachment.id] = attachment
        self._publish(attachment, None)
        return attachment

    def detach(self, attachment_id: str) -> None:
        attachment = self._attachments.pop(attachment_id, None)
        if attachment is not None:
            self._remove("attachment", attachment.id, None)

    # ---- backend updates -----------------------------------------------

    def observe(self, msg: be.Message) -> None:
        """Apply a backend update and publish the resulting state changes."""
        if self._closed:
            return
        match msg:
            case be.Starting(message=text):
                self._observe_starting(text)
            case be.Running(marimo_version=version):
                self._observe_running(version)
            case be.Exited(reason=reason):
                self._observe_exited(reason)
            case _:
                self._state.observe(msg, self._runtime)

    def _observe_starting(self, text: str | None) -> None:
        if self._runtime is None:
            # Track kernels started outside the host API.
            self._set_runtime(self._new_runtime("starting", text, None))
        elif self._runtime.status == "failed":
            self._replace_runtime(text)
        elif self._runtime.status == "starting":
            self._set_runtime(replace(self._runtime, message=text))

    def _observe_running(self, version: str | None) -> None:
        if self._runtime is None:
            self._set_runtime(self._new_runtime("running", None, version))
            return
        if self._runtime.status == "failed":
            self._replace_runtime()
        if self._runtime.status in ("starting", "running"):
            self._set_runtime(
                replace(
                    self._runtime,
                    status="running",
                    message=None,
                    marimo_version=version,
                )
            )

    def _observe_exited(self, reason: str | None) -> None:
        runtime = self._runtime
        if runtime is None:
            return
        if runtime.status == "terminating" and self._replacement is not None:
            replacement, self._replacement = self._replacement, None
            request_id = self._lifecycle_request
            self._end_runtime()
            self._lifecycle_request = request_id
            self._set_runtime(replacement)
            assert self._runtime is not None
            self._backend.start(self._runtime.id)
        elif runtime.status == "terminating":
            self._end_runtime()
        else:
            # Preserve results after an unexpected exit.
            self._state.interrupt("failed")
            self._set_runtime(
                replace(runtime, status="failed", message=reason)
            )

    def _replace_runtime(self, text: str | None = None) -> None:
        request_id = self._lifecycle_request
        self._end_runtime()
        self._lifecycle_request = request_id
        self._set_runtime(self._new_runtime("starting", text, None))

    def _new_runtime(
        self,
        status: protocol.RuntimeStatus,
        text: str | None,
        version: str | None,
    ) -> protocol.Runtime:
        return protocol.Runtime(
            id=mint(protocol.RuntimeId, "rt"),
            notebook_id=self.id,
            status=status,
            message=text,
            marimo_version=version,
            started_at=utcnow(),
        )

    # ---- stream --------------------------------------------------------

    def _snapshot(self) -> list[Event]:
        """Return notebook objects as snapshot events, parents first."""
        bodies: list[protocol.Runtime | protocol.Attachment] = []
        if self._runtime is not None:
            bodies.append(self._runtime)
        bodies.extend(self._attachments.values())
        return [
            Event(
                kind_of(body),
                message(body),
                notebook_id=self.id,
            )
            for body in bodies
        ] + self._state.snapshot()

    def _dispose(self, *, request_id: str | None = None) -> None:
        """Close the notebook and remove its state, children first.

        The host must publish `notebook.removed` after disposing of its state.
        """
        self._closed = True
        self._state.interrupt()
        self._state.clear()
        for attachment_id in list(self._attachments):
            self.detach(attachment_id)
        if self._runtime is not None:
            runtime, self._runtime = self._runtime, None
            self._remove("runtime", runtime.id, request_id)

    def _publish(
        self,
        body: protocol.Runtime | protocol.Attachment,
        request_id: str | None,
    ) -> None:
        self._stream.publish(
            body,
            notebook_id=self.id,
            request_id=request_id,
        )

    def _remove(
        self,
        kind: str,
        object_id: str,
        request_id: str | None,
    ) -> None:
        self._stream.remove(
            kind,
            object_id,
            notebook_id=self.id,
            request_id=request_id,
        )
