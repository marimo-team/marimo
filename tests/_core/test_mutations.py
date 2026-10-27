# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio

import msgspec
import pytest

from marimo._core import protocol
from marimo._core.calls import (
    EditCall,
    MutationHeaders,
    NotebookParams,
    OperationCall,
    SaveCall,
    SaveHeaders,
    StopCall,
    dispatch,
)
from marimo._core.operations import Mutations, Reply
from tests._core.test_notebook_document import put

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
        return await dispatch(mutations, bridge, call)

    return serve


def kind(reply: Reply) -> str:
    _, body = reply
    assert isinstance(body, protocol.Problem)
    return body.type.rsplit("/", 1)[1]


async def test_edit_retry_and_atomic_conflict(bridge, serve):
    events = []
    bridge.host.subscribe(events.append, notebook_id=NOTEBOOK)
    call = edit("edit", put("c1", "x = 2", "*"))
    status, result = await serve(call)
    assert status == 200
    assert isinstance(result, protocol.EditResponse)
    event_count = len(events)
    assert event_count > 0
    assert await serve(call) == (200, result)
    assert (bridge.edits, len(events)) == (1, event_count)

    conflict = await serve(
        edit(
            "conflict", put("new", "y = 1", None), put("c1", "x = 3", "stale")
        )
    )
    assert conflict[0] == 409
    assert isinstance(conflict[1], protocol.Problem)
    assert conflict[1].edit.change == 1
    assert conflict[1].edit.cell.code == "x = 2"
    assert len(events) == event_count
    notebook = await bridge.host.notebook(NOTEBOOK)
    assert [cell.id for cell in notebook.document] == ["c1"]


async def test_cancellation_and_concurrent_retry(bridge, serve):
    bridge.release.clear()
    call = edit("edit", put("c1", "x = 2", "*"))
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
    assert kind(await serve(edit("edit", put("c1", "x = 2", "stale")))) == (
        "conflict"
    )
    status, _ = await serve(edit("edit", put("c1", "x = 2", "*")))
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
