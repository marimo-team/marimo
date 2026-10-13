# Copyright 2026 Marimo. All rights reserved.
"""Notebook runtimes, client attachments, and runs.

Runtime and run commands call a backend. `Notebook.observe` applies
backend updates and publishes events.
"""

from __future__ import annotations

from time import monotonic
from typing import TYPE_CHECKING, Any

import msgspec
from msgspec.structs import replace

from marimo._core import backend as be, protocol
from marimo._core.errors import Conflict, NoRuntime, NotFound
from marimo._core.execution_state import ExecutionState, RetentionPolicy
from marimo._core.ids import mint
from marimo._core.stream import Event, kind_of, message, utcnow

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._core.stream import Body, Stream


class Notebook:
    """A document, its results, and the runtime that produces them.

    Clients attach to a notebook, edit it, and run it. Every change is
    published as an event so that each client sees the same notebook.
    Commands change it and call the backend, which reports back through
    `observe`.

    Subscribers hear about a command once it has reached the backend.
    Results survive runtime stops and restarts, and the host decides how
    long completed scratch results are kept. Commands on a notebook the
    host has removed raise `NotFound`.
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
        # Correlate runtime events with the pending start, stop, or restart.
        self._runtime_request: str | None = None

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
        with self._stream.deferred():
            self._require_open()
            if self._runtime is not None:
                return self._runtime, False
            runtime = self._new_runtime("starting", None, None)
            self._runtime_request = request_id
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
        with self._stream.deferred():
            self._require_open()
            runtime = self._require_runtime()
            self._runtime_request = request_id
            self._replacement = None
            if runtime.status == "terminating":
                return runtime
            terminating = replace(runtime, status="terminating")
            self._set_runtime(terminating)
            if runtime.status == "failed":
                self._end_runtime()
            else:
                self._backend.stop(runtime.id)
            return terminating

    def restart(self, *, request_id: str | None = None) -> protocol.Runtime:
        """Stop the runtime and start a replacement with a new ID.

        Returns the replacement in its starting state. The replacement
        appears on the stream after the old runtime is removed.

        Raises:
            NoRuntime: If the notebook has no runtime.
            Conflict: If the runtime is not running.
        """
        with self._stream.deferred():
            self._require_open()
            runtime = self._require_runtime()
            if runtime.status != "running":
                raise Conflict(
                    f"the runtime is {runtime.status}; only a running one restarts"
                )
            self._runtime_request = request_id
            replacement = self._new_runtime("starting", None, None)
            self._replacement = replacement
            terminating = replace(runtime, status="terminating")
            self._set_runtime(terminating)
            self._backend.stop(runtime.id)
            return replacement

    # TODO: Remove once sessions start their runtime through `start`.
    # marimo still creates kernels for browser tabs behind the notebook's
    # back, so the host learns about them afterwards.
    def adopt(
        self, attach: Callable[[protocol.RuntimeId], None]
    ) -> protocol.Runtime:
        """Track a kernel started outside the host API.

        Returns a starting runtime. Calls `attach` with its ID before
        delivering events to subscribers. The callback binds the backend
        synchronously and reports status, including attachment failures,
        through `observe`.

        Raises:
            Conflict: If the notebook has a runtime that has not failed.
        """
        with self._stream.deferred():
            self._require_open()
            if self._runtime is not None:
                if self._runtime.status != "failed":
                    raise Conflict(
                        f"the notebook has a {self._runtime.status} runtime"
                    )
                self._end_runtime()
            runtime = self._new_runtime("starting", None, None)
            self._set_runtime(runtime)
            attach(runtime.id)
            return runtime

    def _require_runtime(self) -> protocol.Runtime:
        if self._runtime is None:
            raise NoRuntime(
                f"notebook {self.id} has no runtime; start one first."
            )
        return self._runtime

    def _set_runtime(self, runtime: protocol.Runtime) -> None:
        self._runtime = runtime
        self._publish(runtime, self._runtime_request)
        if runtime.status in ("running", "failed"):
            self._runtime_request = None

    def _end_runtime(self) -> None:
        assert self._runtime is not None
        self._state.interrupt()
        runtime, self._runtime = self._runtime, None
        self._remove("runtime", runtime.id, self._runtime_request)
        self._runtime_request = None

    # ---- runs ----------------------------------------------------------

    def run(self, code: str, *, request_id: str) -> protocol.Run:
        """Queue scratch code on the runtime.

        The host assigns the run ID. Request IDs correlate events. The
        host retains retry receipts separately from execution results.

        Raises:
            NoRuntime: If the notebook has no runtime.
            Conflict: If the runtime is not running, or a run is in progress.
        """
        with self._stream.deferred():
            self._require_open()
            runtime = self._require_runtime()
            if runtime.status != "running":
                raise Conflict(f"the runtime is {runtime.status}.")
            if (active := self._state.active_run) is not None:
                raise Conflict(f"run {active.id} is in progress.")
            run = protocol.Run(
                id=mint(protocol.RunId, "run"),
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

    def attach(
        self,
        *,
        identity: str | None = None,
        kind: str | None = None,
        name: str | None = None,
    ) -> protocol.Attachment:
        """Attach a client to this notebook.

        Each call creates a separate attachment. `identity` is stored as
        data. It does not affect the attachment lifetime. An omitted `kind`
        is `client`. An empty `name` is stored as null.

        Raises:
            msgspec.ValidationError: If a value breaks the protocol's
                constraints on the attachment field of the same name.
        """
        self._require_open()
        fields: dict[str, Any] = {
            "id": mint(protocol.AttachmentId, "att"),
            "notebook_id": self.id,
            "kind": kind or "client",
            "name": name or None,
            "since": utcnow(),
        }
        if identity is not None:
            fields["identity"] = identity
        attachment = msgspec.convert(fields, protocol.Attachment)
        self._attachments[attachment.id] = attachment
        self._publish(attachment, None)
        return attachment

    def detach(self, attachment_id: str) -> None:
        """Remove the attachment and publish its removal.

        Unknown IDs are ignored.
        """
        attachment = self._attachments.pop(attachment_id, None)
        if attachment is not None:
            self._remove("attachment", attachment.id, None)

    # ---- backend updates -----------------------------------------------

    def observe(self, msg: be.Message) -> None:
        """Apply a backend update and publish the resulting state changes."""
        if self._closed:
            return
        match msg:
            case be.Starting() | be.Running() | be.Exited():
                runtime = self._runtime
                if runtime is None or msg.runtime_id != runtime.id:
                    return  # A kernel this notebook no longer tracks.
                self._observe_runtime(runtime, msg)
            case _:
                self._state.observe(msg, self._runtime)

    def _observe_runtime(
        self, runtime: protocol.Runtime, report: be.RuntimeReport
    ) -> None:
        match report:
            case be.Starting(message=text):
                if runtime.status == "starting":
                    self._set_runtime(replace(runtime, message=text))
            case be.Running(marimo_version=version):
                if runtime.status in ("starting", "running"):
                    self._set_runtime(
                        replace(
                            runtime,
                            status="running",
                            message=None,
                            marimo_version=version,
                        )
                    )
            case be.Exited(reason=reason):
                self._observe_exited(runtime, reason)

    def _observe_exited(
        self, runtime: protocol.Runtime, reason: str | None
    ) -> None:
        if runtime.status == "terminating" and self._replacement is not None:
            replacement, self._replacement = self._replacement, None
            request_id = self._runtime_request
            with self._stream.deferred():
                self._end_runtime()
                self._runtime_request = request_id
                self._set_runtime(replacement)
                self._backend.start(replacement.id)
        elif runtime.status == "terminating":
            self._end_runtime()
        else:
            # Preserve results after an unexpected exit.
            self._state.interrupt("failed")
            self._set_runtime(
                replace(runtime, status="failed", message=reason)
            )

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

    def emit(
        self,
        type: str,  # noqa: A002
        data: Any,
        *,
        request_id: str | None = None,
    ) -> protocol.Custom:
        """Publish a custom event on the notebook stream.

        A custom event is a notebook occurrence with a producer-defined
        payload.

        Raises:
            TypeError: If `data` is not a JSON value.
            ValueError: If `type` is empty.
        """
        self._require_open()
        if not type:
            raise ValueError("type must be a non-empty string")
        # Fail here, in the producer, instead of inside every subscriber's
        # stream when the event is framed.
        msgspec.json.encode(data)
        custom = protocol.Custom(type=type, data=data)
        self._publish(custom, request_id)
        return custom

    # ---- stream --------------------------------------------------------

    def _snapshot(self) -> list[Event]:
        """Return notebook objects as snapshot events, parents first.

        Runs, executions, and outputs keep their insertion order.
        """
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

    def _publish(self, body: Body, request_id: str | None) -> None:
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
