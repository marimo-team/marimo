# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio

import msgspec
import pytest

from marimo._core import backend as be, protocol
from marimo._core.calls import (
    MutationHeaders,
    UIElementFunctionCall,
    UIElementParams,
    UIElementSendCall,
    UIElementSendRequest,
    dispatch,
)
from marimo._core.document import Document, DocumentCell
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.operations import Mutations
from tests._core.conftest import (
    RecordingBridge,
    ScriptedBackend,
    add_notebook,
    project,
    record,
    runtime_id_of,
)


def publish(notebook: Notebook) -> None:
    notebook.observe(
        be.UIElementCreated(
            runtime_id_of(notebook),
            protocol.UIElement(
                id="c1-0",
                kind="element",
                cell_id=protocol.CellId("c1"),
                config=protocol.UIElementConfig(
                    component="test", label=None, args={}
                ),
                state=protocol.UIElementState(None),
            ),
        )
    )


class SendingBackend(ScriptedBackend):
    def __init__(self) -> None:
        super().__init__()
        self.sent: asyncio.Queue[str] = asyncio.Queue()

    def send_ui_element(
        self,
        element_id: str,
        message: protocol.UIElementFunctionCall,
        call_id: str,
    ) -> None:
        super().send_ui_element(element_id, message, call_id)
        self.sent.put_nowait(call_id)


async def setup():
    host = Host(operations=("ui_element.send", "ui_element.update"))
    host.update_project(project())
    backend = SendingBackend()
    notebook = await add_notebook(
        host,
        msgspec.structs.replace(record(), operations=tuple(host.operations)),
        backend,
        document=Document(
            [DocumentCell(protocol.CellId("c1"), "slider = None")], {}
        ),
    )
    notebook.adopt(lambda _: None)
    notebook.observe(be.Running(runtime_id_of(notebook)))
    publish(notebook)
    bridge = RecordingBridge(host)
    mutations = Mutations(host)
    return notebook, backend, bridge, mutations


def call(key: str = "retry") -> UIElementSendCall:
    return UIElementSendCall(
        UIElementParams(protocol.NotebookId("n1"), "c1-0"),
        MutationHeaders(key),
        UIElementSendRequest(
            UIElementFunctionCall(function="search", args={})
        ),
    )


def result(notebook: Notebook, call_id: str, value: object = None) -> None:
    notebook.observe(
        be.UIElementResult(
            runtime_id_of(notebook),
            call_id,
            protocol.UIElementFunctionResult(
                status=protocol.UIElementFunctionStatus(
                    code="ok", title=None, message=None
                ),
                return_value=value,
                found=True,
            ),
        )
    )


async def submitted(backend: SendingBackend, count: int = 1) -> list[str]:
    async with asyncio.timeout(2):
        return [await backend.sent.get() for _ in range(count)]


async def test_results_are_correlated_private_and_retried_once() -> None:
    notebook, backend, bridge, mutations = await setup()
    before = bridge.host.events(None, notebook_id=notebook.id)
    events = []
    bridge.host.subscribe(events.append)
    first = asyncio.create_task(dispatch(mutations, bridge, call("one")))
    second = asyncio.create_task(dispatch(mutations, bridge, call("two")))
    ids = await submitted(backend, 2)
    retry = asyncio.create_task(dispatch(mutations, bridge, call("one")))
    result(notebook, "unknown", "ignore")
    result(notebook, ids[1], "second")
    result(notebook, ids[0], {"rows": [1]})
    one, two, again = await asyncio.gather(first, second, retry)
    assert one == again
    assert one[0] == two[0] == 200
    assert isinstance(one[1], protocol.UIElementSendResponse)
    assert one[1].result.return_value == {"rows": [1]}
    assert isinstance(two[1], protocol.UIElementSendResponse)
    assert two[1].result.return_value == "second"
    assert len(backend.calls) == 2
    assert not notebook._ui_element_calls
    assert not events
    assert bridge.host.events(None, notebook_id=notebook.id) == before


async def test_disconnected_waiter_does_not_cancel_accepted_work() -> None:
    notebook, backend, bridge, mutations = await setup()
    waiter = asyncio.create_task(dispatch(mutations, bridge, call()))
    [call_id] = await submitted(backend)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    result(notebook, call_id)
    status, body = await dispatch(mutations, bridge, call())
    assert status == 200
    assert isinstance(body, protocol.UIElementSendResponse)
    assert body.result.return_value is None
    assert len(backend.calls) == 1


async def test_timeout_is_retained_and_late_reply_is_ignored(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "marimo._core.notebook.UI_ELEMENT_RESULT_TIMEOUT", 0.01
    )
    notebook, backend, bridge, mutations = await setup()
    status, body = await dispatch(mutations, bridge, call())
    assert status == 504
    assert isinstance(body, protocol.Problem)
    assert body.type.endswith("/timeout")
    result(notebook, str(backend.calls[0][3]), "too late")
    assert await dispatch(mutations, bridge, call()) == (status, body)
    assert len(backend.calls) == 1
    assert not notebook._ui_element_calls


@pytest.mark.parametrize("action", ["remove", "stop", "close"])
async def test_lifetime_ends_pending_calls(action: str) -> None:
    notebook, backend, bridge, mutations = await setup()
    waiter = asyncio.create_task(dispatch(mutations, bridge, call()))
    [call_id] = await submitted(backend)
    if action == "remove":
        notebook.observe(
            be.UIElementsRemoved(
                runtime_id_of(notebook), protocol.CellId("c1")
            )
        )
        publish(notebook)
        result(notebook, call_id, "old instance")
    elif action == "stop":
        notebook.observe(be.Exited(runtime_id_of(notebook)))
    else:
        bridge.host.remove_notebook(notebook.id)
    status, body = await waiter
    assert status == 404
    assert not notebook._ui_element_calls
    assert await dispatch(mutations, bridge, call()) == (status, body)
    assert len(backend.calls) == 1


async def test_send_permission_is_independent_of_update() -> None:
    _, backend, bridge, mutations = await setup()
    bridge.host.update_notebook(
        msgspec.structs.replace(
            bridge.host.notebooks["n1"], operations=("ui_element.update",)
        )
    )
    status, _ = await dispatch(mutations, bridge, call())
    assert status == 403
    assert not backend.calls


@pytest.mark.parametrize(
    "message",
    [
        {},
        {"function": "search", "args": []},
        {"function": "search", "args": {}, "extra": 1},
    ],
)
def test_send_rejects_malformed_messages(message: object) -> None:
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert({"message": message}, type=UIElementSendRequest)
