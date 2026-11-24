# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio

import msgspec
import pytest

from marimo._core import protocol
from marimo._core.calls import (
    EditCall,
    EmitCall,
    MutationHeaders,
    NotebookParams,
    OperationCall,
    SaveCall,
    SaveHeaders,
    StopCall,
    dispatch,
)
from marimo._core.operations import Mutations, Reply
from tests._core.test_notebook_document import create, replace_cell

NOTEBOOK = protocol.NotebookId("n1")
PARAMS = NotebookParams(NOTEBOOK)


def edit(key: str, *changes: protocol.Change) -> EditCall:
    return EditCall(
        PARAMS, MutationHeaders(key), protocol.EditRequest(changes)
    )


def save(key: str, if_match: str | None = None) -> SaveCall:
    return SaveCall(PARAMS, SaveHeaders(key, if_match), protocol.SaveRequest())


@pytest.fixture
def serve(bridge):
    mutations = Mutations(bridge.host)

    async def serve(call: OperationCall) -> Reply:
        return await dispatch(mutations, bridge, call, request=None)

    return serve


def kind(reply: Reply) -> str:
    _, body = reply
    assert body is not None
    kind: str = msgspec.to_builtins(body)["type"]
    return kind.rsplit(":", 1)[1]


async def test_edit_retry_and_atomic_conflict(bridge, serve):
    events = []
    bridge.host.subscribe(events.append, notebook_id=NOTEBOOK)
    call = edit("edit", replace_cell("c1", "x = 2", "*"))
    status, result = await serve(call)
    assert status == 200
    assert isinstance(result, protocol.EditResponse)
    event_count = len(events)
    assert event_count > 0
    assert await serve(call) == (200, result)
    assert (bridge.edits, len(events)) == (1, event_count)

    conflict = await serve(
        edit(
            "conflict",
            create("new", "y = 1"),
            replace_cell("c1", "x = 3", "stale"),
        )
    )
    assert conflict[0] == 412
    assert isinstance(conflict[1], protocol.PreconditionFailedProblem)
    assert conflict[1].index == 1
    assert conflict[1].cell.code == "x = 2"
    assert len(events) == event_count
    notebook = await bridge.host.notebook(NOTEBOOK)
    assert [cell.id for cell in notebook.document] == ["c1"]


async def test_cancellation_and_concurrent_retry(bridge, serve):
    bridge.release.clear()
    call = edit("edit", replace_cell("c1", "x = 2", "*"))
    first = asyncio.create_task(serve(call))
    await asyncio.wait_for(bridge.started.wait(), 5)
    try:
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        retry = asyncio.create_task(serve(call))
        bridge.release.set()
        status, result = await asyncio.wait_for(retry, 5)
        assert status == 200
        assert isinstance(result, protocol.EditResponse)
        assert bridge.edits == 1
    finally:
        bridge.release.set()


async def test_receipts_include_operation_and_preconditions(bridge, serve):
    saved = await serve(save("save", '"a", W/"weak", "b"'))
    assert saved[0] == 200
    assert await serve(save("save", '"a", W/"weak", "b"')) == saved
    assert kind(await serve(save("save", '"c"'))) == "conflict"
    assert kind(await serve(edit("save"))) == "conflict"
    assert bridge.preconditions == [("a", "b")]


async def test_rejected_calls_do_not_reserve_keys(serve):
    assert kind(
        await serve(edit("edit", replace_cell("c1", "x = 2", "stale")))
    ) == ("precondition-failed")
    status, _ = await serve(edit("edit", replace_cell("c1", "x = 2", "*")))
    assert status == 200


async def test_calls_check_capabilities_and_keys(bridge, serve):
    stop = StopCall(PARAMS, MutationHeaders("stop"))
    assert kind(await serve(stop)) == "unsupported-operation"
    assert kind(await serve(edit(""))) == "invalid-request"
    bridge.host.update_notebook(
        msgspec.structs.replace(bridge.host.notebooks[NOTEBOOK], operations=())
    )
    assert kind(await serve(edit("edit"))) == "forbidden"
    assert bridge.edits == 0


async def test_emit_permission_is_independent_of_editing(bridge, serve):
    call = EmitCall(
        PARAMS,
        MutationHeaders("emit"),
        protocol.EmitRequest(type="example.message", data=None),
    )
    for operations, expected in [
        (("notebook.edit",), "forbidden"),
        (("notebook.emit",), None),
    ]:
        bridge.host.update_notebook(
            msgspec.structs.replace(
                bridge.host.notebooks[NOTEBOOK], operations=operations
            )
        )
        reply = await serve(call)
        if expected is None:
            assert reply == (204, None)
        else:
            assert kind(reply) == expected
