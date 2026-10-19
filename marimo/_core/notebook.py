# Copyright 2026 Marimo. All rights reserved.
"""Notebook state and commands."""

from __future__ import annotations

import asyncio
import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Any

import msgspec
from msgspec.structs import replace

from marimo._core import backend as be, protocol
from marimo._core.document import Stale
from marimo._core.errors import Conflict, EditConflict, NoRuntime, NotFound
from marimo._core.executions import Executions, Released, Removed
from marimo._core.ids import mint
from marimo._core.stream import Event, Kind, kind_of, message, utcnow

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from marimo._core.analysis import Analyzer
    from marimo._core.document import (
        Changed,
        Document,
        DocumentCell,
    )
    from marimo._core.executions import Change
    from marimo._core.stream import Body, Sink


LOGGER = logging.getLogger(__name__)


class Notebook:
    """A document, its execution results, and the runtime that produces them.

    The notebook gives the document its identity and its saved revision,
    and publishes the records clients read. The document
    and cell results remain when the runtime stops. Commands call the
    backend and publish changes through the sink. Change the document
    and executions through the notebook so each change reaches the sink.

    With an analyzer, the notebook requests analysis of each document
    revision and publishes the result when that revision is still
    current. The previous analysis stays until then.
    """

    def __init__(
        self,
        notebook_id: protocol.NotebookId,
        document: Document,
        executions: Executions,
        backend: be.Backend,
        sink: Sink,
        *,
        saved_etag: protocol.Etag | None = None,
        analyzer: Analyzer | None = None,
    ) -> None:
        self._id = notebook_id
        self._document = document
        self._saved_etag = saved_etag
        # Versions order the records clients read. The document's advances
        # with each change to its content; a cell's is the document version
        # at which it was created or last changed.
        self._version = 1
        self._cell_versions = {cell.id: 1 for cell in document}
        # The document record as last published, so a change that leaves
        # it the same publishes nothing.
        self._published: protocol.Document | None = self._document_record
        self._executions = executions
        self.backend = backend
        self.sink = sink
        self._analyzer = analyzer
        self._closed = False
        self._runtime: protocol.Runtime | None = None
        self._attachments: dict[str, protocol.Attachment] = {}
        self._replacement: protocol.Runtime | None = None
        # Correlate runtime events with the pending start, stop, or restart.
        self._runtime_request: str | None = None
        self._analysis: protocol.Analysis | None = None
        self._analysis_task: asyncio.Task[None] | None = None
        # Whether the document changed during analysis, and that request.
        self._reanalyze = False
        self._reanalyze_request: str | None = None
        self._request_analysis(None)

    @property
    def document(self) -> Document:
        """The current revision. The notebook's commands produce the next."""
        return self._document

    @property
    def executions(self) -> Executions:
        """The execution results owned by this notebook."""
        return self._executions

    @property
    def id(self) -> protocol.NotebookId:
        return self._id

    @property
    def saved_etag(self) -> protocol.Etag | None:
        """The document revision the store holds, if known."""
        return self._saved_etag

    def require_revision(self, etags: Sequence[str]) -> None:
        """Check that the document is at one of `etags`.

        Raises:
            EditConflict: If it is not, carrying the document as it is.
        """
        self._require_open()
        if self.document.etag not in etags:
            raise EditConflict(
                "The document has changed since it was read",
                change=0,
                cell=None,
                document=self._document_record,
            )

    @property
    def _document_record(self) -> protocol.Document:
        """The document as clients read it, built from its current state."""
        document = self._document
        return protocol.Document(
            notebook_id=self._id,
            order=tuple(cell.id for cell in document),
            app_config=deepcopy(dict(document.app_config)),
            etag=document.etag,
            saved_etag=self._saved_etag,
            order_etag=document.order_etag,
            app_config_etag=document.app_config_etag,
            version=self._version,
        )

    @property
    def runtime(self) -> protocol.Runtime | None:
        """The current runtime, if any."""
        return self._runtime

    @property
    def analysis(self) -> protocol.Analysis | None:
        """The latest analysis, which may describe an earlier revision."""
        return self._analysis

    def _require_open(self) -> None:
        if self._closed:
            raise NotFound(f"no notebook {self.id}")

    # ---- document ------------------------------------------------------

    def replace(
        self,
        cells: Sequence[DocumentCell],
        app_config: Mapping[str, object],
        *,
        saved: bool = False,
        request_id: str | None = None,
    ) -> protocol.EditResponse:
        """Replace the document and publish its changes.

        With `saved`, the new contents are also the persisted revision.
        The response carries the version of each cell that changed, and
        `None` for each cell that was removed.
        """
        self._require_open()
        self._document, changed = self._document.replace(cells, app_config)
        if saved:
            self._saved_etag = self._document.etag
        self._publish_changed(changed, request_id)
        versions: dict[str, protocol.CellVersion | None] = {
            cell.id: self._cell_version(cell) for cell in changed.cells
        }
        for cell_id in changed.removed:
            versions[cell_id] = None
        return protocol.EditResponse(
            document=self._document_record, cells=versions
        )

    def edit(
        self, changes: Sequence[protocol.Change], *, request_id: str
    ) -> protocol.EditResponse:
        """Apply an edit as one unit and publish its effects.

        Raises:
            EditConflict: If a precondition is stale. Nothing is applied.
            Invalid: If a change could not apply to any state.
        """
        self._require_open()
        result = self._document.apply(changes)
        if isinstance(result, Stale):
            cell = (
                None
                if result.cell_id is None
                else self._document.cell(result.cell_id)
            )
            raise EditConflict(
                f"change {result.change} names a state the document no "
                "longer has",
                change=result.change,
                cell=None if cell is None else self._cell_record(cell),
                document=self._document_record,
            )
        self._document, applied = result
        self._publish_changed(applied.changed, request_id)
        return protocol.EditResponse(
            document=self._document_record,
            cells={
                cell_id: None if cell is None else self._cell_version(cell)
                for cell_id, cell in applied.cells.items()
            },
        )

    def mark_saved(
        self, etag: protocol.Etag, *, request_id: str | None = None
    ) -> protocol.Document:
        """Record `etag` as the persisted revision and return the document.

        The revision may precede the current one, when the document
        changed while it was being written.
        """
        self._require_open()
        self._saved_etag = etag
        published = self._refresh()
        if published is not None:
            self._publish(published, request_id)
        return self._document_record

    def _cell_record(self, cell: DocumentCell) -> protocol.Cell:
        return protocol.Cell(
            id=cell.id,
            notebook_id=self._id,
            code=cell.code,
            name=cell.name,
            config=cell.config,
            etag=cell.etag,
            code_hash=cell.code_hash,
            version=self._cell_versions[cell.id],
        )

    def _cell_version(self, cell: DocumentCell) -> protocol.CellVersion:
        return protocol.CellVersion(
            etag=cell.etag,
            code_hash=cell.code_hash,
            version=self._cell_versions[cell.id],
        )

    def _refresh(self) -> protocol.Document | None:
        """Return the document record when it differs from the last published."""
        record = self._document_record
        if record == self._published:
            return None
        self._published = record
        return record

    def _publish_changed(
        self, changed: Changed, request_id: str | None
    ) -> None:
        """Publish a document change, then analyze the new revision."""
        if changed:
            self._version += 1
            for cell in changed.cells:
                self._cell_versions[cell.id] = self._version
            for cell_id in changed.removed:
                self._cell_versions.pop(cell_id, None)
        with self.sink.deferred():
            for cell in changed.cells:
                self._publish(self._cell_record(cell), request_id)
            for cell_id in changed.removed:
                self._apply(
                    self.executions.remove_cell(protocol.CellId(cell_id))
                )
                self._remove("cell", cell_id, request_id)
            record = self._refresh()
            if record is not None:
                self._publish(record, request_id)
        if changed.etag is not None:
            self._request_analysis(request_id)

    # ---- analysis ------------------------------------------------------

    def _request_analysis(self, request_id: str | None) -> None:
        """Analyze the current revision, or after the one in progress."""
        if self._analyzer is None or self._closed:
            return
        if self._analysis_task is not None:
            self._reanalyze, self._reanalyze_request = True, request_id
            return
        self._analysis_task = asyncio.create_task(
            self._analyze(self._document, request_id)
        )

    async def _analyze(
        self, document: Document, request_id: str | None
    ) -> None:
        assert self._analyzer is not None
        try:
            while not self._closed:
                etag = document.etag
                try:
                    cells = await self._analyzer.analyze(document)
                except Exception:
                    LOGGER.exception("Could not analyze document %s", etag)
                else:
                    if not self._closed and etag == self._document.etag:
                        self._analysis = protocol.Analysis(
                            notebook_id=self.id,
                            document_etag=etag,
                            cells={
                                cid: analysis
                                for cid, analysis in cells.items()
                            },
                        )
                        self._publish(self._analysis, request_id)
                if not self._reanalyze or self._closed:
                    return
                request_id = self._reanalyze_request
                self._reanalyze, self._reanalyze_request = False, None
                document = self._document
        finally:
            self._analysis_task = None

    # ---- runtime -------------------------------------------------------

    def start(
        self, *, request_id: str | None = None
    ) -> tuple[protocol.Runtime, bool]:
        """Return the runtime and whether this call started it."""
        with self.sink.deferred():
            self._require_open()
            if self._runtime is not None:
                return self._runtime, False
            runtime = self._new_runtime("starting", None, None)
            self._runtime_request = request_id
            self._set_runtime(runtime)
            self.backend.start(runtime.id)
            return runtime, True

    def stop(self, *, request_id: str | None = None) -> protocol.Runtime:
        """Stop the runtime and retain its results.

        The runtime stays until the backend reports its exit. A failed runtime
        is removed immediately.
        """
        with self.sink.deferred():
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
                self.backend.stop(runtime.id)
            return terminating

    def restart(self, *, request_id: str | None = None) -> protocol.Runtime:
        """Stop a running runtime and return its replacement.

        The replacement starts after the old runtime exits.
        """
        with self.sink.deferred():
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
            self.backend.stop(runtime.id)
            return replacement

    # TODO: Remove once sessions start their runtime through `start`.
    # Browser sessions create kernels outside the notebook.
    def adopt(
        self, attach: Callable[[protocol.RuntimeId], None]
    ) -> protocol.Runtime:
        """Attach the backend to an existing kernel.

        Calls `attach` with a new runtime ID before delivering events.
        """
        with self.sink.deferred():
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
        self._apply(self.executions.interrupt())
        runtime, self._runtime = self._runtime, None
        self._remove("runtime", runtime.id, self._runtime_request)
        self._runtime_request = None

    # ---- runs ----------------------------------------------------------

    def run(self, code: str, *, request_id: str) -> protocol.Run:
        """Queue scratch code on a running, idle runtime."""
        with self.sink.deferred():
            self._require_open()
            runtime = self._require_runtime()
            if runtime.status != "running":
                raise Conflict(f"the runtime is {runtime.status}.")
            active = self.executions.active()
            if active is not None:
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
            self._apply(self.executions.begin(run, request_id))
            self.backend.run(run.id, code)
            return run

    def interrupt(self, run_id: str) -> protocol.Run:
        """Request interruption of a run in progress."""
        self._require_open()
        run = self.executions.run(protocol.RunId(run_id))
        if run is None:
            raise NotFound(f"notebook {self.id} has no run {run_id}.")
        if run.status == "completed":
            raise Conflict(f"run {run_id} has already ended.")
        self.backend.interrupt(run.id)
        return run

    # ---- attachments ---------------------------------------------------

    def attach(
        self,
        *,
        identity: str | None = None,
        kind: str | None = None,
        name: str | None = None,
    ) -> protocol.Attachment:
        """Create a client attachment.

        Identity is metadata. Each attachment has its own lifetime.
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
        """Remove an attachment if it exists."""
        attachment = self._attachments.pop(attachment_id, None)
        if attachment is not None:
            self._remove("attachment", attachment.id, None)

    # ---- backend updates -----------------------------------------------

    def observe(self, msg: be.Message) -> None:
        """Apply a backend report and publish what changed."""
        if self._closed:
            return
        match msg:
            case be.Starting() | be.Running() | be.Exited():
                runtime = self._runtime
                if runtime is None or msg.runtime_id != runtime.id:
                    return  # A kernel this notebook no longer tracks.
                self._observe_runtime(runtime, msg)
            case _:
                self._apply(self.executions.observe(msg, self._runtime))

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
            with self.sink.deferred():
                self._end_runtime()
                self._runtime_request = request_id
                self._set_runtime(replacement)
                self.backend.start(replacement.id)
        elif runtime.status == "terminating":
            self._end_runtime()
        else:
            # Preserve results after an unexpected exit.
            self._apply(self.executions.interrupt("failed"))
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
        """Publish a named custom event with a JSON payload."""
        self._require_open()
        if not type:
            raise ValueError("type must be a non-empty string")
        # Validate before delivering to subscribers.
        msgspec.json.encode(data)
        custom = protocol.Custom(type=type, data=data)
        self._publish(custom, request_id)
        return custom

    # ---- stream --------------------------------------------------------

    def _snapshot(self) -> list[Event]:
        """Return current state as events in dependency order."""
        bodies: list[Body] = [
            *(self._cell_record(cell) for cell in self.document),
            self._document_record,
        ]
        if self._analysis is not None:
            bodies.append(self._analysis)
        if self._runtime is not None:
            bodies.append(self._runtime)
        bodies.extend(self._attachments.values())
        events = [
            Event(kind_of(body), message(body), notebook_id=self.id)
            for body in bodies
        ]
        executions = self.executions
        for record in executions._records():
            run_id = executions.run_id_of(record)
            events.append(
                Event(
                    kind_of(record),
                    message(
                        record, request_id=executions.snapshot_request(run_id)
                    ),
                    notebook_id=self.id,
                    run_id=run_id,
                )
            )
        return events

    def _dispose(self, *, request_id: str | None = None) -> None:
        """Close the notebook and remove its state, children first.

        The host publishes `notebook.removed` after disposing of this state.
        """
        self._closed = True
        if self._analysis_task is not None:
            self._analysis_task.cancel()
        self._apply(self.executions.interrupt())
        self._apply(self.executions.clear())
        for attachment_id in list(self._attachments):
            self.detach(attachment_id)
        if self._runtime is not None:
            runtime, self._runtime = self._runtime, None
            self._remove("runtime", runtime.id, request_id)

    def _publish(self, body: Body, request_id: str | None) -> None:
        self.sink.publish(
            body,
            notebook_id=self.id,
            request_id=request_id,
        )

    def _remove(
        self,
        kind: Kind,
        object_id: str,
        request_id: str | None,
    ) -> None:
        self.sink.remove(
            kind,
            object_id,
            notebook_id=self.id,
            request_id=request_id,
        )

    def _apply(self, changes: Sequence[Change]) -> None:
        """Publish changes and release completed runs."""
        executions = self.executions
        with self.sink.deferred():
            for change in changes:
                if isinstance(change, Released):
                    executions.release(change.run_id)
                    self.backend.forget(change.run_id)
                    continue
                run_id = executions.run_id_of(change)
                request_id = executions.request_id(run_id)
                if isinstance(change, Removed):
                    self.sink.remove(
                        change.kind,
                        change.id,
                        notebook_id=self.id,
                        run_id=run_id,
                        request_id=request_id,
                    )
                else:
                    self.sink.publish(
                        change,
                        notebook_id=self.id,
                        run_id=run_id,
                        request_id=request_id,
                    )
