# Copyright 2026 Marimo. All rights reserved.
"""Handlers for the host's operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

import msgspec

from marimo._core import protocol
from marimo._core.errors import (
    Conflict,
    HostError,
    NotFound,
    Unsupported,
)
from marimo._core.operations import Reply
from marimo._core.result import Err, Ok, Result

if TYPE_CHECKING:
    from marimo._core.backend import RequestInfo
    from marimo._core.operations import Mutations, NotebookBridge

api = protocol.api


_T = TypeVar("_T")
_P = TypeVar("_P")
_P_co = TypeVar("_P_co", covariant=True)


class _Described(Protocol[_P_co]):
    """An error that names its problem."""

    def problem(self) -> _P_co: ...


def answered(outcome: Result[_T, _Described[_P]]) -> Result[_T, _P]:
    """Describe an error as its problem."""
    if outcome.ok:
        return outcome
    return Err(outcome.error.problem())


def _unoffered(call: api.Call) -> Unsupported:
    return Unsupported(
        f"This host does not offer {call.__struct_config__.tag}"
    )


class HostHandlers(api.Host.Handlers):
    """The catalog operations, which this host does not offer."""

    async def create(
        self, call: api.Host.Create.Call
    ) -> api.Host.Create.Result:
        raise _unoffered(call)


class NotebookHandlers(api.Notebook.Handlers):
    """The operations on a notebook, for one request."""

    def __init__(
        self,
        bridge: NotebookBridge,
        *,
        request: RequestInfo | None = None,
        allow_input: bool = False,
    ) -> None:
        self._bridge = bridge
        self._request = request
        self._allow_input = allow_input

    async def edit(
        self, call: api.Notebook.Edit.Call
    ) -> api.Notebook.Edit.Result:
        return answered(
            await self._bridge.edit(
                call.params.notebook_id,
                call.body.changes,
                request_id=call.headers.idempotency_key,
            )
        )

    async def emit(
        self, call: api.Notebook.Emit.Call
    ) -> api.Notebook.Emit.Result:
        notebook = await self._bridge.host.notebook(call.params.notebook_id)
        notebook.emit(
            call.body.type,
            call.body.data,
            request_id=call.headers.idempotency_key,
        )
        return Ok(None)

    async def save(
        self, call: api.Notebook.Save.Call
    ) -> api.Notebook.Save.Result:
        decisions = call.body.decisions
        return answered(
            await self._bridge.save(
                call.params.notebook_id,
                if_match=_if_match(call.headers.if_match),
                decisions={} if decisions is msgspec.UNSET else decisions,
                request_id=call.headers.idempotency_key,
            )
        )

    async def start(
        self, call: api.Notebook.Start.Call
    ) -> api.Notebook.Start.Result:
        notebook = await self._bridge.host.notebook(call.params.notebook_id)
        runtime, created = notebook.start(
            request_id=call.headers.idempotency_key
        )
        return Ok((202 if created else 200, runtime))

    async def stop(
        self, call: api.Notebook.Stop.Call
    ) -> api.Notebook.Stop.Result:
        notebook = await self._bridge.host.notebook(call.params.notebook_id)
        return answered(notebook.stop(request_id=call.headers.idempotency_key))

    async def restart(
        self, call: api.Notebook.Restart.Call
    ) -> api.Notebook.Restart.Result:
        notebook = await self._bridge.host.notebook(call.params.notebook_id)
        return answered(
            notebook.restart(request_id=call.headers.idempotency_key)
        )

    async def run(
        self, call: api.Notebook.Run.Call
    ) -> api.Notebook.Run.Result:
        notebook = await self._bridge.host.notebook(call.params.notebook_id)
        return answered(
            notebook.run(
                cells=call.body.cells,
                request_id=call.headers.idempotency_key,
                request=self._request,
                allow_input=self._allow_input,
            )
        )

    async def execute(
        self, call: api.Notebook.Execute.Call
    ) -> api.Notebook.Execute.Result:
        notebook = await self._bridge.host.notebook(call.params.notebook_id)
        return answered(
            notebook.run(
                call.body.code,
                request_id=call.headers.idempotency_key,
                request=self._request,
                allow_input=self._allow_input,
            )
        )

    async def interrupt(
        self, call: api.Notebook.Interrupt.Call
    ) -> api.Notebook.Interrupt.Result:
        notebook = await self._bridge.host.notebook(call.params.notebook_id)
        return answered(
            notebook.interrupt(request_id=call.headers.idempotency_key)
        )

    async def cancel(
        self, call: api.Notebook.Cancel.Call
    ) -> api.Notebook.Cancel.Result:
        notebook_id, run_id = call.params.notebook_id, call.params.run_id
        notebook = await self._bridge.host.notebook(notebook_id)
        try:
            return Ok(
                notebook.cancel(
                    run_id, request_id=call.headers.idempotency_key
                )
            )
        except NotFound:
            run = self._bridge.host.run(notebook_id, run_id)
            if run is not None and isinstance(
                run.state, protocol.RunCompleted
            ):
                raise Conflict(f"run {run_id} has already ended.") from None
            raise

    async def reply(
        self, call: api.Notebook.Reply.Call
    ) -> api.Notebook.Reply.Result:
        notebook_id, input_id = call.params.notebook_id, call.params.input_id
        notebook = await self._bridge.host.notebook(notebook_id)
        try:
            return Ok(
                notebook.reply_input(
                    input_id,
                    call.body.value,
                    request_id=call.headers.idempotency_key,
                )
            )
        except NotFound:
            if self._bridge.host.input(notebook_id, input_id) is not None:
                raise Conflict(
                    f"input {input_id} has already ended."
                ) from None
            raise

    async def update(
        self, call: api.Notebook.Update.Call
    ) -> api.Notebook.Update.Result:
        raise _unoffered(call)

    async def delete(
        self, call: api.Notebook.Delete.Call
    ) -> api.Notebook.Delete.Result:
        raise _unoffered(call)

    async def open(
        self, call: api.Notebook.Open.Call
    ) -> api.Notebook.Open.Result:
        raise _unoffered(call)


async def dispatch(
    mutations: Mutations, served: api.Api, call: api.Call
) -> Reply:
    """Serve a call once per idempotency key."""
    try:
        outcome = await mutations.execute(
            str(call.__struct_config__.tag),
            notebook_id=None
            if isinstance(call, api.Host.Create.Call)
            else call.params.notebook_id,
            key=call.headers.idempotency_key,
            payload=call,
            call=lambda: served.handle(call),
        )
    except HostError as e:
        failure = e.problem()
        return failure.status, failure
    if outcome.ok:
        return outcome.value
    problem = outcome.error
    return problem.status, problem


def _if_match(header: str | None) -> tuple[str, ...] | None:
    """Parse strong entity tags; weak tags never satisfy an If-Match check."""
    if header is None or header.strip() == "*":
        return None
    return tuple(
        part.strip().strip('"')
        for part in header.split(",")
        if part.strip() and not part.strip().startswith("W/")
    )
