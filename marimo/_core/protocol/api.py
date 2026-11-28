# Copyright 2026 Marimo. All rights reserved.
# AUTO-GENERATED FILE — DO NOT EDIT.
# Generated from packages/host-protocol.
# Regenerate with `make host-protocol-codegen`.
"""Calls, results, and handlers for each host operation."""

from __future__ import annotations

from typing import (
    Final,
    Literal,
    Protocol,
    TypeAlias,
    TypeVar,
    assert_never,
    final,
)

import msgspec

from marimo._core import protocol, result

CommonProblem: TypeAlias = (
    protocol.InvalidRequestProblem
    | protocol.ForbiddenProblem
    | protocol.NotFoundProblem
    | protocol.InternalProblem
)
MutationProblem: TypeAlias = (
    CommonProblem
    | protocol.ConflictProblem
    | protocol.UnsupportedOperationProblem
)


class Host:
    class Create:
        """Create a notebook."""

        ID: Final = "notebook.create"
        METHOD: Final = "POST"
        PATH: Final = "/notebooks"

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="notebook.create",
        ):
            headers: Host.Create.Headers
            body: protocol.CreateNotebookRequest

        Result: TypeAlias = result.Result[protocol.Notebook, MutationProblem]

    class Handlers(Protocol):
        async def create(self, call: Host.Create.Call) -> Host.Create.Result:
            """Create a notebook."""
            ...


class Notebook:
    class Delete:
        """Delete a notebook."""

        ID: Final = "notebook.delete"
        METHOD: Final = "DELETE"
        PATH: Final = "/notebooks/{notebook_id}"

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="notebook.delete",
        ):
            params: Notebook.Delete.Params
            headers: Notebook.Delete.Headers

        Result: TypeAlias = result.Result[None, MutationProblem]

    class Edit:
        """Change parts of the document."""

        ID: Final = "notebook.edit"
        METHOD: Final = "POST"
        PATH: Final = "/notebooks/{notebook_id}/edits"

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="notebook.edit",
        ):
            params: Notebook.Edit.Params
            headers: Notebook.Edit.Headers
            body: protocol.EditRequest

        Result: TypeAlias = result.Result[
            protocol.EditResponse,
            MutationProblem | protocol.PreconditionFailedProblem,
        ]

    class Open:
        """Show a notebook in the host's own interface."""

        ID: Final = "notebook.open"
        METHOD: Final = "POST"
        PATH: Final = "/notebooks/{notebook_id}/open"

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="notebook.open",
        ):
            params: Notebook.Open.Params
            headers: Notebook.Open.Headers

        Result: TypeAlias = result.Result[
            protocol.OpenNotebookResponse, MutationProblem
        ]

    class Reply:
        """Answer an execution's pending input."""

        ID: Final = "input.reply"
        METHOD: Final = "POST"
        PATH: Final = (
            "/notebooks/{notebook_id}/runtime/inputs/{input_id}/reply"
        )

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId
            input_id: protocol.ItemId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="input.reply",
        ):
            params: Notebook.Reply.Params
            headers: Notebook.Reply.Headers
            body: protocol.InputReplyRequest

        Result: TypeAlias = result.Result[protocol.Input, MutationProblem]

    class Interrupt:
        """Interrupt the notebook's runtime."""

        ID: Final = "runtime.interrupt"
        METHOD: Final = "POST"
        PATH: Final = "/notebooks/{notebook_id}/runtime/interrupt"

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="runtime.interrupt",
        ):
            params: Notebook.Interrupt.Params
            headers: Notebook.Interrupt.Headers

        Result: TypeAlias = result.Result[
            protocol.Runtime, MutationProblem | protocol.NoRuntimeProblem
        ]

    class Cancel:
        """Cancel a run."""

        ID: Final = "runtime.cancel"
        METHOD: Final = "DELETE"
        PATH: Final = "/notebooks/{notebook_id}/runtime/runs/{run_id}"

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId
            run_id: protocol.RunId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="runtime.cancel",
        ):
            params: Notebook.Cancel.Params
            headers: Notebook.Cancel.Headers

        Result: TypeAlias = result.Result[protocol.Run, MutationProblem]

    class Restart:
        """Restart the notebook's kernel."""

        ID: Final = "runtime.restart"
        METHOD: Final = "POST"
        PATH: Final = "/notebooks/{notebook_id}/runtime/restart"

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="runtime.restart",
        ):
            params: Notebook.Restart.Params
            headers: Notebook.Restart.Headers

        Result: TypeAlias = result.Result[
            protocol.Runtime, MutationProblem | protocol.NoRuntimeProblem
        ]

    class Run:
        """Run notebook cells."""

        ID: Final = "runtime.run"
        METHOD: Final = "POST"
        PATH: Final = "/notebooks/{notebook_id}/runtime/runs"

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="runtime.run",
        ):
            params: Notebook.Run.Params
            headers: Notebook.Run.Headers
            body: protocol.RunRequest

        Result: TypeAlias = result.Result[
            protocol.Run,
            MutationProblem
            | protocol.NoRuntimeProblem
            | protocol.PreconditionFailedProblem,
        ]

    class Execute:
        """Execute Python with notebook values."""

        ID: Final = "runtime.execute"
        METHOD: Final = "POST"
        PATH: Final = "/notebooks/{notebook_id}/runtime/execute"

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="runtime.execute",
        ):
            params: Notebook.Execute.Params
            headers: Notebook.Execute.Headers
            body: protocol.ExecuteRequest

        Result: TypeAlias = result.Result[
            protocol.Run, MutationProblem | protocol.NoRuntimeProblem
        ]

    class Start:
        """Start the notebook's runtime, or find the one it has."""

        ID: Final = "runtime.start"
        METHOD: Final = "PUT"
        PATH: Final = "/notebooks/{notebook_id}/runtime"

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="runtime.start",
        ):
            params: Notebook.Start.Params
            headers: Notebook.Start.Headers
            body: protocol.StartRuntimeRequest

        Result: TypeAlias = result.Result[
            tuple[Literal[200, 202], protocol.Runtime],
            MutationProblem | protocol.DecisionRequiredProblem,
        ]

    class Stop:
        """Stop the notebook's runtime."""

        ID: Final = "runtime.stop"
        METHOD: Final = "DELETE"
        PATH: Final = "/notebooks/{notebook_id}/runtime"

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="runtime.stop",
        ):
            params: Notebook.Stop.Params
            headers: Notebook.Stop.Headers

        Result: TypeAlias = result.Result[
            protocol.Runtime, MutationProblem | protocol.NoRuntimeProblem
        ]

    class Save:
        """Write the document to the host's store."""

        ID: Final = "notebook.save"
        METHOD: Final = "POST"
        PATH: Final = "/notebooks/{notebook_id}/save"

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")
            if_match: str | None = msgspec.field(name="if-match", default=None)

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="notebook.save",
        ):
            params: Notebook.Save.Params
            headers: Notebook.Save.Headers
            body: protocol.SaveRequest

        Result: TypeAlias = result.Result[
            protocol.EditResponse,
            MutationProblem
            | protocol.PreconditionFailedProblem
            | protocol.DecisionRequiredProblem,
        ]

    class Update:
        """Rename or move a notebook."""

        ID: Final = "notebook.update"
        METHOD: Final = "PATCH"
        PATH: Final = "/notebooks/{notebook_id}"

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="notebook.update",
        ):
            params: Notebook.Update.Params
            headers: Notebook.Update.Headers
            body: protocol.UpdateNotebookRequest

        Result: TypeAlias = result.Result[protocol.Notebook, MutationProblem]

    class Emit:
        """Publish a custom event."""

        ID: Final = "notebook.emit"
        METHOD: Final = "POST"
        PATH: Final = "/notebooks/{notebook_id}/emit"

        class Params(msgspec.Struct, frozen=True):
            notebook_id: protocol.NotebookId

        class Headers(msgspec.Struct, frozen=True):
            idempotency_key: str = msgspec.field(name="idempotency-key")

        class Call(
            msgspec.Struct,
            frozen=True,
            tag_field="operation",
            tag="notebook.emit",
        ):
            params: Notebook.Emit.Params
            headers: Notebook.Emit.Headers
            body: protocol.EmitRequest

        Result: TypeAlias = result.Result[None, MutationProblem]

    class Handlers(Protocol):
        async def delete(
            self, call: Notebook.Delete.Call
        ) -> Notebook.Delete.Result:
            """Delete a notebook."""
            ...

        async def edit(self, call: Notebook.Edit.Call) -> Notebook.Edit.Result:
            """Change parts of the document."""
            ...

        async def open(self, call: Notebook.Open.Call) -> Notebook.Open.Result:
            """Show a notebook in the host's own interface."""
            ...

        async def reply(
            self, call: Notebook.Reply.Call
        ) -> Notebook.Reply.Result:
            """Answer an execution's pending input."""
            ...

        async def interrupt(
            self, call: Notebook.Interrupt.Call
        ) -> Notebook.Interrupt.Result:
            """Interrupt the notebook's runtime."""
            ...

        async def cancel(
            self, call: Notebook.Cancel.Call
        ) -> Notebook.Cancel.Result:
            """Cancel a run."""
            ...

        async def restart(
            self, call: Notebook.Restart.Call
        ) -> Notebook.Restart.Result:
            """Restart the notebook's kernel."""
            ...

        async def run(self, call: Notebook.Run.Call) -> Notebook.Run.Result:
            """Run notebook cells."""
            ...

        async def execute(
            self, call: Notebook.Execute.Call
        ) -> Notebook.Execute.Result:
            """Execute Python with notebook values."""
            ...

        async def start(
            self, call: Notebook.Start.Call
        ) -> Notebook.Start.Result:
            """Start the notebook's runtime, or find the one it has."""
            ...

        async def stop(self, call: Notebook.Stop.Call) -> Notebook.Stop.Result:
            """Stop the notebook's runtime."""
            ...

        async def save(self, call: Notebook.Save.Call) -> Notebook.Save.Result:
            """Write the document to the host's store."""
            ...

        async def update(
            self, call: Notebook.Update.Call
        ) -> Notebook.Update.Result:
            """Rename or move a notebook."""
            ...

        async def emit(self, call: Notebook.Emit.Call) -> Notebook.Emit.Result:
            """Publish a custom event."""
            ...


Operation: TypeAlias = (
    type[Host.Create]
    | type[Notebook.Delete]
    | type[Notebook.Edit]
    | type[Notebook.Open]
    | type[Notebook.Reply]
    | type[Notebook.Interrupt]
    | type[Notebook.Cancel]
    | type[Notebook.Restart]
    | type[Notebook.Run]
    | type[Notebook.Execute]
    | type[Notebook.Start]
    | type[Notebook.Stop]
    | type[Notebook.Save]
    | type[Notebook.Update]
    | type[Notebook.Emit]
)

OPERATIONS: tuple[Operation, ...] = (
    Host.Create,
    Notebook.Delete,
    Notebook.Edit,
    Notebook.Open,
    Notebook.Reply,
    Notebook.Interrupt,
    Notebook.Cancel,
    Notebook.Restart,
    Notebook.Run,
    Notebook.Execute,
    Notebook.Start,
    Notebook.Stop,
    Notebook.Save,
    Notebook.Update,
    Notebook.Emit,
)

Call: TypeAlias = (
    Host.Create.Call
    | Notebook.Delete.Call
    | Notebook.Edit.Call
    | Notebook.Open.Call
    | Notebook.Reply.Call
    | Notebook.Interrupt.Call
    | Notebook.Cancel.Call
    | Notebook.Restart.Call
    | Notebook.Run.Call
    | Notebook.Execute.Call
    | Notebook.Start.Call
    | Notebook.Stop.Call
    | Notebook.Save.Call
    | Notebook.Update.Call
    | Notebook.Emit.Call
)

Result: TypeAlias = result.Result[
    tuple[int, msgspec.Struct | None], protocol.Problem
]

_T = TypeVar("_T")
_E = TypeVar("_E")


def _answered(
    status: int, outcome: result.Result[_T, _E]
) -> result.Result[tuple[int, _T], _E]:
    if outcome.ok:
        return result.Ok((status, outcome.value))
    return outcome


@final
class Api:
    """Serves each call with its group's handler."""

    def __init__(
        self, *, host: Host.Handlers, notebook: Notebook.Handlers
    ) -> None:
        self._host = host
        self._notebook = notebook

    async def handle(self, call: Call) -> Result:
        match call:
            case Host.Create.Call():
                return _answered(201, await self._host.create(call))
            case Notebook.Delete.Call():
                return _answered(204, await self._notebook.delete(call))
            case Notebook.Edit.Call():
                return _answered(200, await self._notebook.edit(call))
            case Notebook.Open.Call():
                return _answered(200, await self._notebook.open(call))
            case Notebook.Reply.Call():
                return _answered(200, await self._notebook.reply(call))
            case Notebook.Interrupt.Call():
                return _answered(202, await self._notebook.interrupt(call))
            case Notebook.Cancel.Call():
                return _answered(202, await self._notebook.cancel(call))
            case Notebook.Restart.Call():
                return _answered(202, await self._notebook.restart(call))
            case Notebook.Run.Call():
                return _answered(202, await self._notebook.run(call))
            case Notebook.Execute.Call():
                return _answered(202, await self._notebook.execute(call))
            case Notebook.Start.Call():
                return await self._notebook.start(call)
            case Notebook.Stop.Call():
                return _answered(202, await self._notebook.stop(call))
            case Notebook.Save.Call():
                return _answered(200, await self._notebook.save(call))
            case Notebook.Update.Call():
                return _answered(200, await self._notebook.update(call))
            case Notebook.Emit.Call():
                return _answered(204, await self._notebook.emit(call))
        assert_never(call)
