# Copyright 2026 Marimo. All rights reserved.
"""Requests for notebook operations, each with the handler that serves it.

A call has the parts of an HTTP request, as the client sends them. Its
`params` are the path parameters, its `headers` the request headers it
reads, and its `body` the decoded request body. A call also gives its place
in the HTTP API, and its `handle` method does the work and declares the
successful status and response in its return type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

import msgspec

from marimo._core import protocol
from marimo._core.errors import Conflict, HostError, Invalid, NotFound
from marimo._core.operations import Reply, problem_for

if TYPE_CHECKING:
    from marimo._core.operations import Mutations, NotebookBridge


class NotebookParams(msgspec.Struct, frozen=True):
    notebook_id: protocol.NotebookId


class RunParams(NotebookParams, frozen=True):
    run_id: protocol.RunId


class MutationHeaders(msgspec.Struct, frozen=True):
    idempotency_key: str = msgspec.field(name="idempotency-key", default="")


class SaveHeaders(MutationHeaders, frozen=True):
    if_match: str | None = msgspec.field(name="if-match", default=None)


class _Call(msgspec.Struct, frozen=True, tag_field="operation"):
    METHOD: ClassVar[str]
    PATH: ClassVar[str]


class EditCall(_Call, frozen=True, tag="notebook.edit"):
    """Change parts of the document."""

    METHOD = "POST"
    PATH = "/notebooks/{notebook_id}/edits"

    params: NotebookParams
    headers: MutationHeaders
    body: protocol.EditRequest

    async def handle(
        self, bridge: NotebookBridge
    ) -> tuple[Literal[200], protocol.EditResponse]:
        return 200, await bridge.edit(
            self.params.notebook_id,
            self.body.changes,
            request_id=self.headers.idempotency_key,
        )


class SaveCall(_Call, frozen=True, tag="notebook.save"):
    """Write the document to the host's store."""

    METHOD = "POST"
    PATH = "/notebooks/{notebook_id}/save"

    params: NotebookParams
    headers: SaveHeaders
    body: protocol.SaveRequest

    async def handle(
        self, bridge: NotebookBridge
    ) -> tuple[Literal[200], protocol.EditResponse]:
        decisions = self.body.decisions
        return 200, await bridge.save(
            self.params.notebook_id,
            if_match=_if_match(self.headers.if_match),
            decisions={} if decisions is msgspec.UNSET else decisions,
            request_id=self.headers.idempotency_key,
        )


class StartCall(_Call, frozen=True, tag="runtime.start"):
    """Start the notebook's runtime, or find the one it has."""

    METHOD = "PUT"
    PATH = "/notebooks/{notebook_id}/runtime"

    params: NotebookParams
    headers: MutationHeaders
    body: protocol.StartRuntimeRequest

    async def handle(
        self, bridge: NotebookBridge
    ) -> tuple[Literal[200, 202], protocol.Runtime]:
        notebook = await bridge.host.notebook(self.params.notebook_id)
        runtime, created = notebook.start(
            request_id=self.headers.idempotency_key
        )
        return (202 if created else 200), runtime


class StopCall(_Call, frozen=True, tag="runtime.stop"):
    """Stop the notebook's runtime."""

    METHOD = "DELETE"
    PATH = "/notebooks/{notebook_id}/runtime"

    params: NotebookParams
    headers: MutationHeaders

    async def handle(
        self, bridge: NotebookBridge
    ) -> tuple[Literal[202], protocol.Runtime]:
        notebook = await bridge.host.notebook(self.params.notebook_id)
        return 202, notebook.stop(request_id=self.headers.idempotency_key)


class RestartCall(_Call, frozen=True, tag="runtime.restart"):
    """Restart the notebook's kernel."""

    METHOD = "POST"
    PATH = "/notebooks/{notebook_id}/runtime/restart"

    params: NotebookParams
    headers: MutationHeaders

    async def handle(
        self, bridge: NotebookBridge
    ) -> tuple[Literal[202], protocol.Runtime]:
        notebook = await bridge.host.notebook(self.params.notebook_id)
        return 202, notebook.restart(request_id=self.headers.idempotency_key)


class RunCall(_Call, frozen=True, tag="runtime.run"):
    """Run code or cells against the notebook's runtime."""

    METHOD = "POST"
    PATH = "/notebooks/{notebook_id}/runtime/runs"

    params: NotebookParams
    headers: MutationHeaders
    body: protocol.RunRequest

    async def handle(
        self, bridge: NotebookBridge
    ) -> tuple[Literal[202], protocol.Run]:
        notebook = await bridge.host.notebook(self.params.notebook_id)
        key = self.headers.idempotency_key
        code, cells = self.body.code, self.body.cells
        if isinstance(code, str) and cells is msgspec.UNSET:
            return 202, notebook.run(code, request_id=key)
        if code is msgspec.UNSET and isinstance(cells, tuple):
            return 202, notebook.run(cells=cells, request_id=key)
        raise Invalid("A run names code or cells, not both")


class InterruptCall(_Call, frozen=True, tag="runtime.interrupt"):
    """Interrupt a run."""

    METHOD = "DELETE"
    PATH = "/notebooks/{notebook_id}/runtime/runs/{run_id}"

    params: RunParams
    headers: MutationHeaders

    async def handle(
        self, bridge: NotebookBridge
    ) -> tuple[Literal[202], protocol.Run]:
        notebook_id, run_id = self.params.notebook_id, self.params.run_id
        notebook = await bridge.host.notebook(notebook_id)
        try:
            return 202, notebook.interrupt(run_id)
        except NotFound:
            run = bridge.host.run(notebook_id, run_id)
            if run is not None and run.status == "completed":
                raise Conflict(f"run {run_id} has already ended.") from None
            raise


OperationCall = (
    EditCall
    | SaveCall
    | StartCall
    | StopCall
    | RestartCall
    | RunCall
    | InterruptCall
)
"""A request for any notebook operation, tagged by its operation id."""

# The same members as `OperationCall`, as values to build routes from.
# `typing.get_args` would return them untyped.
CALLS: tuple[type[OperationCall], ...] = (
    EditCall,
    SaveCall,
    StartCall,
    StopCall,
    RestartCall,
    RunCall,
    InterruptCall,
)


async def dispatch(
    mutations: Mutations, bridge: NotebookBridge, call: OperationCall
) -> Reply:
    """Serve a call once per idempotency key and describe a failure as a problem."""
    try:
        return await mutations.execute(
            str(call.__struct_config__.tag),
            notebook_id=call.params.notebook_id,
            key=call.headers.idempotency_key,
            payload=call,
            call=lambda: call.handle(bridge),
        )
    except HostError as e:
        failure = problem_for(e)
        return failure.status, failure


def _if_match(header: str | None) -> tuple[str, ...] | None:
    """Parse strong entity tags; weak tags never satisfy an If-Match check."""
    if header is None or header.strip() == "*":
        return None
    return tuple(
        part.strip().strip('"')
        for part in header.split(",")
        if part.strip() and not part.strip().startswith("W/")
    )
