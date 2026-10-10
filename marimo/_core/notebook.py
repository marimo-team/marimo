# Copyright 2026 Marimo. All rights reserved.
"""Notebook runtimes, client attachments, and runs.

Runtime and run commands call a backend. `Notebook.observe` applies
backend updates and publishes events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from msgspec.structs import replace

from marimo._core import backend as be, protocol
from marimo._core.errors import Conflict, NoRuntime, NotFound
from marimo._core.ids import mint
from marimo._core.stream import Event, kind_of, message, utcnow

if TYPE_CHECKING:
    from marimo._core.stream import Stream

Item = protocol.Console | protocol.Display


class Notebook:
    """A notebook's state and commands.

    Snapshots preserve insertion order for runs, executions, and items.
    Completed results remain available across runtime stops and restarts.
    Removing the notebook closes it; further commands raise `NotFound`.
    """

    def __init__(
        self,
        notebook_id: protocol.NotebookId,
        backend: be.Backend,
        stream: Stream,
    ) -> None:
        self._id = notebook_id
        self._backend = backend
        self._stream = stream
        self._closed = False
        self.runtime: protocol.Runtime | None = None
        self._attachments: dict[str, protocol.Attachment] = {}
        self._runs: dict[str, protocol.Run] = {}
        self._run_requests: dict[str, str | None] = {}
        self._executions: dict[protocol.ExecutionId, protocol.Execution] = {}
        # Superseded results still contribute to their unfinished run.
        self._retired_executions: dict[
            protocol.ExecutionId, protocol.Execution
        ] = {}
        self._items: dict[protocol.ItemId, Item] = {}
        self._replacement: protocol.Runtime | None = None
        # Associate runtime events with the pending start, stop, or restart.
        self._lifecycle_request: str | None = None

    @property
    def id(self) -> protocol.NotebookId:
        return self._id

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
        if self.runtime is not None:
            return self.runtime, False
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
        if self.runtime is None:
            raise NoRuntime(
                f"notebook {self.id} has no runtime; start one first."
            )
        return self.runtime

    def _set_runtime(self, runtime: protocol.Runtime) -> None:
        self.runtime = runtime
        self._publish(runtime, self._lifecycle_request)
        if runtime.status in ("running", "failed"):
            self._lifecycle_request = None

    def _end_runtime(self) -> None:
        assert self.runtime is not None
        self._interrupt_in_flight()
        runtime, self.runtime = self.runtime, None
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
        run = self._runs.get(request_id)
        if run is not None:
            return run
        runtime = self._require_runtime()
        if runtime.status != "running":
            raise Conflict(f"the runtime is {runtime.status}.")
        in_flight = [r for r in self._runs.values() if r.status != "completed"]
        if in_flight:
            raise Conflict(f"run {in_flight[0].id} is in progress.")
        run = protocol.Run(
            id=protocol.RunId(request_id),
            notebook_id=self.id,
            caused_by=None,
            status="queued",
            outcome=None,
            started_at=None,
            completed_at=None,
        )
        self._run_requests[run.id] = request_id
        self._set_run(run)
        self._backend.run(run.id, code)
        return run

    def interrupt(self, run_id: str) -> protocol.Run:
        """Request interruption of a run in progress.

        Raises:
            NotFound: If there is no such run.
            Conflict: If the run is already completed.
        """
        self._require_open()
        run = self._runs.get(run_id)
        if run is None:
            raise NotFound(f"notebook {self.id} has no run {run_id}.")
        if run.status == "completed":
            raise Conflict(f"run {run_id} has already ended.")
        self._backend.interrupt(run.id)
        return run

    def _clear_runs(self) -> None:
        self._retired_executions.clear()
        for item in list(self._items.values()):
            del self._items[item.id]
            run_id = self._executions[item.execution_id].run_id
            self._remove(kind_of(item), item.id, run_id, run_id=run_id)
        for execution in list(self._executions.values()):
            del self._executions[execution.id]
            self._remove(
                "execution",
                execution.id,
                execution.run_id,
                run_id=execution.run_id,
            )
        for run in list(self._runs.values()):
            del self._runs[run.id]
            self._remove("run", run.id, run.id, run_id=run.id)
            self._run_requests.pop(run.id, None)

    def _set_run(self, run: protocol.Run) -> None:
        self._runs[run.id] = run
        self._publish(run, run.id)

    def _set_execution(self, execution: protocol.Execution) -> None:
        self._executions[execution.id] = execution
        self._publish(execution, execution.run_id)

    def _interrupt_in_flight(
        self, outcome: protocol.RunOutcome = "interrupted"
    ) -> None:
        now = utcnow()
        for execution in list(self._executions.values()):
            if execution.status != "completed":
                self._set_execution(
                    replace(
                        execution,
                        status="completed",
                        outcome=protocol.InterruptedOutcome(),
                        completed_at=now,
                    )
                )
        for run in list(self._runs.values()):
            if run.status != "completed":
                self._set_run(
                    replace(
                        run,
                        status="completed",
                        outcome=outcome,
                        completed_at=now,
                    )
                )
        self._retired_executions.clear()

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
            case be.Scheduled(run_id=run_id, caused_by=caused_by):
                if run_id not in self._runs:
                    self._require_runtime()
                    self._run_requests[run_id] = None
                    self._set_run(
                        protocol.Run(
                            id=run_id,
                            notebook_id=self.id,
                            caused_by=caused_by,
                            status="queued",
                            outcome=None,
                            started_at=None,
                            completed_at=None,
                        )
                    )
            case be.Planned(run_id=run_id, executions=planned):
                self._observe_planned(run_id, planned)
            case be.Status(execution_id=execution_id, status=status):
                self._observe_status(execution_id, status)
            case be.Produced(item=item):
                if item.execution_id in self._executions:
                    self._items[item.id] = item
                    self._publish(
                        item, self._executions[item.execution_id].run_id
                    )
            case be.Concluded(execution_id=execution_id, outcome=outcome):
                if (
                    execution := self._executions.get(execution_id)
                ) is not None and execution.status != "completed":
                    self._set_execution(replace(execution, outcome=outcome))
            case be.Done(run_id=run_id, outcome=outcome):
                if (
                    run := self._runs.get(run_id)
                ) is not None and run.status != "completed":
                    members = [
                        execution
                        for execution in (
                            *self._executions.values(),
                            *self._retired_executions.values(),
                        )
                        if execution.run_id == run_id
                    ]
                    if any(
                        execution.status != "completed"
                        for execution in members
                    ):
                        raise ValueError(
                            "a run cannot complete with unfinished executions"
                        )
                    if outcome == "succeeded" and any(
                        not isinstance(
                            execution.outcome, protocol.ValueOutcome
                        )
                        for execution in members
                    ):
                        raise ValueError(
                            "a successful run cannot contain failed or interrupted executions"
                        )
                    self._set_run(
                        replace(
                            run,
                            status="completed",
                            outcome=outcome,
                            completed_at=utcnow(),
                        )
                    )
                    for member in members:
                        self._retired_executions.pop(member.id, None)

    def _observe_starting(self, text: str | None) -> None:
        if self.runtime is None:
            # Track kernels started outside the host API.
            self._set_runtime(self._new_runtime("starting", text, None))
        elif self.runtime.status == "failed":
            self._replace_runtime(text)
        elif self.runtime.status == "starting":
            self._set_runtime(replace(self.runtime, message=text))

    def _observe_running(self, version: str | None) -> None:
        if self.runtime is None:
            self._set_runtime(self._new_runtime("running", None, version))
            return
        if self.runtime.status == "failed":
            self._replace_runtime()
        if self.runtime.status in ("starting", "running"):
            self._set_runtime(
                replace(
                    self.runtime,
                    status="running",
                    message=None,
                    marimo_version=version,
                )
            )

    def _observe_exited(self, reason: str | None) -> None:
        runtime = self.runtime
        if runtime is None:
            return
        if runtime.status == "terminating" and self._replacement is not None:
            replacement, self._replacement = self._replacement, None
            request_id = self._lifecycle_request
            self._end_runtime()
            self._lifecycle_request = request_id
            self._set_runtime(replacement)
            assert self.runtime is not None
            self._backend.start(self.runtime.id)
        elif runtime.status == "terminating":
            self._end_runtime()
        else:
            # Preserve results after an unexpected exit.
            self._interrupt_in_flight("failed")
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

    def _observe_planned(
        self,
        run_id: protocol.RunId,
        planned: tuple[be.PlannedExecution, ...],
    ) -> None:
        if (
            run := self._runs.get(run_id)
        ) is None or run.status == "completed":
            return
        runtime = self._require_runtime()
        for entry in planned:
            if (
                entry.id in self._executions
                or entry.id in self._retired_executions
            ):
                continue
            if entry.cell_id is not None:
                for previous in list(self._executions.values()):
                    if previous.cell_id == entry.cell_id:
                        self._retire_execution(previous)
            self._set_execution(
                protocol.Execution(
                    id=entry.id,
                    run_id=run_id,
                    runtime_id=runtime.id,
                    caused_by=entry.caused_by,
                    cell_id=entry.cell_id,
                    code=entry.code,
                    code_hash=entry.code_hash,
                    bindings=[],
                    status="queued",
                    outcome=None,
                    stale=None,
                    started_at=None,
                    completed_at=None,
                )
            )

    def _retire_execution(self, execution: protocol.Execution) -> None:
        if execution.status != "completed":
            raise ValueError("cannot replace an unfinished cell execution")
        run_id = execution.run_id
        run = self._runs.get(run_id) if run_id is not None else None
        if run is not None and run.status != "completed":
            self._retired_executions[execution.id] = execution
        for item in list(self._items.values()):
            if item.execution_id == execution.id:
                del self._items[item.id]
                self._remove(kind_of(item), item.id, run_id, run_id=run_id)
        del self._executions[execution.id]
        self._remove("execution", execution.id, run_id, run_id=run_id)

    def _observe_status(
        self, execution_id: protocol.ExecutionId, status: protocol.Lifecycle
    ) -> None:
        execution = self._executions.get(execution_id)
        if execution is None or execution.status in (status, "completed"):
            return
        now = utcnow()
        if status == "running":
            execution = replace(execution, status=status, started_at=now)
            assert execution.run_id is not None
            run = self._runs[execution.run_id]
            if run.status == "queued":
                self._set_run(replace(run, status="running", started_at=now))
        elif status == "completed":
            if execution.outcome is None:
                raise ValueError("a completed execution must have an outcome")
            execution = replace(execution, status=status, completed_at=now)
        else:
            execution = replace(execution, status=status)
        self._set_execution(execution)

    # ---- stream --------------------------------------------------------

    def _snapshot(self) -> list[Event]:
        """Return notebook objects as snapshot events, parents first."""
        bodies: list[
            protocol.Runtime
            | protocol.Attachment
            | protocol.Run
            | protocol.Execution
            | Item
        ] = []
        if self.runtime is not None:
            bodies.append(self.runtime)
        bodies.extend(self._attachments.values())
        bodies.extend(self._runs.values())
        bodies.extend(self._executions.values())
        bodies.extend(self._items.values())
        return [
            Event(
                kind_of(body),
                message(body),
                notebook_id=self.id,
                run_id=self._run_id(body),
            )
            for body in bodies
        ]

    def _dispose(self, *, request_id: str | None = None) -> None:
        """Close the notebook and remove its state, children first.

        The host must publish `notebook.removed` after disposing of its state.
        """
        self._closed = True
        self._clear_runs()
        for attachment_id in list(self._attachments):
            self.detach(attachment_id)
        if self.runtime is not None:
            runtime, self.runtime = self.runtime, None
            self._remove("runtime", runtime.id, request_id)

    def _publish(
        self,
        body: protocol.Runtime
        | protocol.Attachment
        | protocol.Run
        | protocol.Execution
        | Item,
        request_id: str | None,
    ) -> None:
        if (run_id := self._run_id(body)) is not None:
            request_id = self._run_requests.get(run_id)
        self._stream.publish(
            body,
            notebook_id=self.id,
            request_id=request_id,
            run_id=self._run_id(body),
        )

    def _run_id(
        self,
        body: protocol.Runtime
        | protocol.Attachment
        | protocol.Run
        | protocol.Execution
        | Item,
    ) -> protocol.RunId | None:
        if isinstance(body, protocol.Run):
            return body.id
        if isinstance(body, protocol.Execution):
            return body.run_id
        if isinstance(body, (protocol.Console, protocol.Display)):
            return self._executions[body.execution_id].run_id
        return None

    def _remove(
        self,
        kind: str,
        object_id: str,
        request_id: str | None,
        *,
        run_id: protocol.RunId | None = None,
    ) -> None:
        if run_id is not None:
            request_id = self._run_requests.get(run_id)
        self._stream.remove(
            kind,
            object_id,
            notebook_id=self.id,
            request_id=request_id,
            run_id=run_id,
        )
