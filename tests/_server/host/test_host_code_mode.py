# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest
from msgspec.structs import replace

from marimo._core import protocol
from marimo._messaging.host import DocumentRequest
from marimo._runtime.commands import DocumentReplyCommand
from tests._server.host.drive import finished, wait_for
from tests._server.host.live import key, open_host

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from starlette.applications import Starlette

    from tests._server.host.drive import Response


@pytest.fixture
async def host(
    tmp_path: Path,
) -> AsyncIterator[tuple[Starlette, str, Response]]:
    source = (
        "import marimo\napp = marimo.App()\n"
        "@app.cell\ndef _():\n    x = 1\n    return (x,)\n"
        "@app.cell\ndef _():\n    y = 2\n    return (y,)\n"
    )
    async with open_host(tmp_path, source) as host:
        yield host


async def submit(
    app: Starlette, notebook_id: str, code: str, request_id: str
) -> str:
    response = await finished(
        app,
        "POST",
        f"/notebooks/{notebook_id}/runtime/execute",
        headers=key(request_id),
        body=json.dumps({"code": code}).encode(),
    )
    assert response.status == 202
    return response.json()["id"]


async def completed(events: Response, run_id: str) -> dict[str, Any]:
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("id") == run_id
            and r["data"]["run"]["status"] == "completed"
            for r in response.records
        ),
    )
    return next(
        r["data"]["run"]
        for r in reversed(events.records)
        if r.get("data", {}).get("run", {}).get("id") == run_id
    )


EDIT = (
    "import marimo._code_mode as cm\n"
    "async with cm.get_context() as ctx:\n"
    "    cell = ctx.cells[0]\n"
    "    assert cell.code == 'x = 1'\n"
    "    ctx.edit_cell(cell.id, code='x = 42')\n"
    "    ctx.run_cell(cell.id)\n"
    "assert ctx.globals['x'] == 42\n"
)


async def test_inline_edit_and_run(host):
    app, notebook_id, events = host
    run_id = await submit(app, notebook_id, EDIT, "agent")
    assert (await completed(events, run_id))["outcome"] == "succeeded"
    notebook = await app.state.host_context.bridge.host.notebook(notebook_id)
    assert [cell.code for cell in notebook.document] == ["x = 42", "y = 2"]
    checked = await submit(
        app,
        notebook_id,
        "assert x == 42\nfrom marimo._runtime.context import get_context\nassert not get_context()._kernel.inline_edits",
        "check",
    )
    assert (await completed(events, checked))["outcome"] == "succeeded"


@pytest.mark.parametrize("same_cell", [False, True])
@pytest.mark.parametrize("run_cells", [False, True])
async def test_competing_edit_before_flush(
    host: tuple[Starlette, str, Response],
    monkeypatch: pytest.MonkeyPatch,
    same_cell: bool,
    run_cells: bool,
) -> None:
    app, notebook_id, events = host
    bridge = app.state.host_context.bridge
    notebook = await bridge.host.notebook(notebook_id)
    session = bridge.session_for_notebook(notebook.id)
    assert session is not None
    assert session.document_request is not None
    original = session.document_request
    read, release = asyncio.Event(), asyncio.Event()

    async def hold_read(request: DocumentRequest) -> DocumentReplyCommand:
        reply = await original(request)
        if request.changes is None and not request.cells:
            read.set()
            await release.wait()
        return reply

    monkeypatch.setattr(session, "document_request", hold_read)
    code = EDIT if run_cells else EDIT.split("    ctx.run_cell", maxsplit=1)[0]
    run_id = await submit(app, notebook_id, code, "agent")
    await asyncio.wait_for(read.wait(), 5)
    cell = list(notebook.document)[0 if same_cell else 1]
    await bridge.edit(
        notebook_id,
        [
            protocol.PutCell(
                base_etag=cell.etag,
                cell=protocol.CellInput(
                    id=cell.id,
                    code="x = 99" if same_cell else "y = 99",
                    name=cell.name,
                    config=cell.config,
                ),
            )
        ],
        request_id="other-edit",
    )
    other = notebook.run(
        cells=[protocol.RequestedCell(id=cell.id)],
        request_id="other-run",
        request=None,
    )
    release.set()
    assert (await completed(events, run_id))["outcome"] == (
        "failed" if same_cell or run_cells else "succeeded"
    )
    assert (await completed(events, other.id))["outcome"] == "succeeded"
    assert [c.code for c in notebook.document] == (
        ["x = 99", "y = 2"]
        if same_cell
        else ["x = 1" if run_cells else "x = 42", "y = 99"]
    )


@pytest.mark.parametrize("migrate", [False, True])
async def test_edit_stays_committed_when_run_source_changes(
    host: tuple[Starlette, str, Response],
    monkeypatch: pytest.MonkeyPatch,
    migrate: bool,
) -> None:
    app, notebook_id, events = host
    bridge = app.state.host_context.bridge
    notebook = await bridge.host.notebook(notebook_id)
    session = bridge.session_for_notebook(notebook.id)
    assert session is not None
    assert session.document_request is not None
    original = session.document_request

    async def edit_again(request: DocumentRequest) -> DocumentReplyCommand:
        reply = await original(request)
        if request.changes is not None:
            cell = next(iter(notebook.document))
            assert cell.code == "x = 42"
            await bridge.edit(
                notebook_id,
                [
                    protocol.PutCell(
                        base_etag=cell.etag,
                        cell=protocol.CellInput(
                            id=cell.id,
                            code="x = 99",
                            name=cell.name,
                            config=cell.config,
                        ),
                    )
                ],
                request_id="competing-edit",
            )
            assert await original(request) == reply
        return reply

    monkeypatch.setattr(session, "document_request", edit_again)
    code = (
        "import marimo._code_mode as cm\n"
        "async with cm.get_context() as ctx:\n"
        "    cell = ctx.cells[0]\n"
        "    assert cell.code == 'x = 1'\n"
        "    ctx.run_cell(cell.id)\n"
        "    ctx.edit_cell(cell.id, code='x = 42', name='setup')\n"
        if migrate
        else EDIT
    )
    run_id = await submit(app, notebook_id, code, "agent")
    assert (await completed(events, run_id))["outcome"] == "failed"
    assert next(iter(notebook.document)).code == "x = 99"
    assert not any(
        r.get("event") == "execution"
        and r["data"]["execution"]["cell_id"]
        == next(iter(notebook.document)).id
        and r["data"]["execution"]["run_id"] == run_id
        for r in events.records
    )


async def test_run_uses_source_accepted_before_a_later_edit(
    host: tuple[Starlette, str, Response], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, notebook_id, events = host
    bridge = app.state.host_context.bridge
    notebook = await bridge.host.notebook(notebook_id)
    session = bridge.session_for_notebook(notebook.id)
    assert session is not None
    assert session.document_request is not None
    original = session.document_request

    async def edit_after_acceptance(
        request: DocumentRequest,
    ) -> DocumentReplyCommand:
        reply = await original(request)
        if request.cells:
            cell = next(iter(notebook.document))
            await bridge.edit(
                notebook_id,
                [
                    protocol.PutCell(
                        base_etag=cell.etag,
                        cell=protocol.CellInput(
                            id=cell.id,
                            code="x = 99",
                            name=cell.name,
                            config=cell.config,
                        ),
                    )
                ],
                request_id="later-edit",
            )
        return reply

    monkeypatch.setattr(session, "document_request", edit_after_acceptance)
    run_id = await submit(app, notebook_id, EDIT, "agent")
    assert (await completed(events, run_id))["outcome"] == "succeeded"
    assert next(iter(notebook.document)).code == "x = 99"


async def test_queued_update_survives_an_abandoned_reply(
    host: tuple[Starlette, str, Response], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, notebook_id, events = host
    bridge = app.state.host_context.bridge
    notebook = await bridge.host.notebook(notebook_id)
    session = bridge.session_for_notebook(notebook.id)
    assert session is not None
    assert session.document_request is not None
    original = session.document_request
    accepted, release = asyncio.Event(), asyncio.Event()

    async def hold_reply(request: DocumentRequest) -> DocumentReplyCommand:
        reply = await original(request)
        if request.changes is not None:
            accepted.set()
            await release.wait()
        return reply

    monkeypatch.setattr(session, "document_request", hold_reply)
    warm = await submit(app, notebook_id, EDIT, "warm")
    await asyncio.wait_for(accepted.wait(), 5)
    release.set()
    assert (await completed(events, warm))["outcome"] == "succeeded"
    accepted.clear()
    release.clear()
    run_id = await submit(
        app,
        notebook_id,
        "import asyncio, marimo._code_mode as cm\n"
        "async with asyncio.timeout(0.5):\n"
        "    async with cm.get_context() as ctx:\n"
        "        ctx.edit_cell(ctx.cells[0].id, disabled=True)\n",
        "abandoned",
    )
    await asyncio.wait_for(accepted.wait(), 5)
    assert (await completed(events, run_id))["outcome"] == "failed"
    release.set()
    checked = await submit(
        app,
        notebook_id,
        "from marimo._runtime.context import get_context\n"
        f"assert get_context().graph.cells[{next(iter(notebook.document)).id!r}].config.disabled\n"
        "assert not get_context()._kernel.inline_edits",
        "check-abandoned",
    )
    assert (await completed(events, checked))["outcome"] == "succeeded"


async def test_fresh_context_reads_edits_without_entering(
    host: tuple[Starlette, str, Response],
) -> None:
    app, notebook_id, events = host
    run_id = await submit(
        app,
        notebook_id,
        "import marimo._code_mode as cm\n"
        "before = cm.get_context()\n"
        "async with cm.get_context() as ctx:\n"
        "    cid = ctx.create_cell('created = 1')\n"
        "assert cm.get_context().cells[cid].code == 'created = 1'\n"
        "assert before.cells[cid].code == 'created = 1'\n",
        "fresh-context",
    )
    assert (await completed(events, run_id))["outcome"] == "succeeded"


async def test_background_tasks_cannot_flush_an_inline_edit(
    host: tuple[Starlette, str, Response],
) -> None:
    app, notebook_id, events = host
    run_id = await submit(
        app,
        notebook_id,
        "import asyncio, marimo._code_mode as cm\n"
        "ctx = cm.get_context()\n"
        "async def background():\n"
        "    try:\n"
        "        async with ctx:\n"
        "            ctx.create_cell('unexpected = 1')\n"
        "    except RuntimeError as error:\n"
        "        assert 'task' in str(error)\n"
        "    else:\n"
        "        raise AssertionError('background context accepted')\n"
        "    try:\n"
        "        async with cm.get_context():\n"
        "            raise AssertionError('background context entered')\n"
        "    except RuntimeError as error:\n"
        "        assert 'task' in str(error)\n"
        "    else:\n"
        "        raise AssertionError('background context created')\n"
        "await asyncio.create_task(background())\n"
        "assert len(ctx.cells) == 2\n",
        "background",
    )
    assert (await completed(events, run_id))["outcome"] == "succeeded"


async def test_synchronous_scratch_can_read_cells(
    host: tuple[Starlette, str, Response],
) -> None:
    app, notebook_id, events = host
    run_id = await submit(
        app,
        notebook_id,
        "import marimo._code_mode as cm\n"
        "assert [cell.code for cell in cm.get_context().cells] == ['x = 1', 'y = 2']\n",
        "sync-read",
    )
    assert (await completed(events, run_id))["outcome"] == "succeeded"


async def test_nested_context_preserves_disjoint_edits(
    host: tuple[Starlette, str, Response],
) -> None:
    app, notebook_id, events = host
    run_id = await submit(
        app,
        notebook_id,
        "import marimo._code_mode as cm\n"
        "async with cm.get_context() as outer:\n"
        "    cell = outer.cells[0]\n"
        "    assert cell.code == 'x = 1'\n"
        "    outer.edit_cell(cell.id, code='x = 42')\n"
        "    outer.run_cell(cell.id)\n"
        "    async with cm.get_context() as inner:\n"
        "        added = inner.create_cell('z = 3')\n"
        "    assert len(outer.cells) == 2\n"
        "assert outer.globals['x'] == 42\n"
        "assert cm.get_context().cells[added].code == 'z = 3'\n",
        "nested",
    )
    assert (await completed(events, run_id))["outcome"] == "succeeded"
    notebook = await app.state.host_context.bridge.host.notebook(notebook_id)
    assert [cell.code for cell in notebook.document] == [
        "x = 42",
        "y = 2",
        "z = 3",
    ]


@pytest.mark.parametrize("operation", ["edit", "run", "edit_and_run"])
async def test_pending_config_rejects_inline_work_until_next_execution(
    host: tuple[Starlette, str, Response],
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    app, notebook_id, events = host
    warm = await submit(app, notebook_id, EDIT, "warm")
    assert (await completed(events, warm))["outcome"] == "succeeded"
    bridge = app.state.host_context.bridge
    notebook = await bridge.host.notebook(notebook_id)
    session = bridge.session_for_notebook(notebook.id)
    assert session is not None
    original = session.document_request
    assert original is not None
    injected = False

    async def disable_before_read(
        request: DocumentRequest,
    ) -> DocumentReplyCommand:
        nonlocal injected
        if not injected:
            injected = True
            cell = next(iter(notebook.document))
            await bridge.edit(
                notebook_id,
                [
                    protocol.PutCell(
                        base_etag=cell.etag,
                        cell=protocol.CellInput(
                            id=cell.id,
                            code=cell.code,
                            name=cell.name,
                            config=replace(cell.config, disabled=True),
                        ),
                    )
                ],
                request_id="browser-disable",
            )
        return await original(request)

    monkeypatch.setattr(session, "document_request", disable_before_read)
    code = (
        "import marimo._code_mode as cm\n"
        "try:\n"
        "    async with cm.get_context() as ctx:\n"
        "        cell = ctx.cells[0]\n"
        "        assert cell.config.disabled\n"
    )
    if operation != "run":
        code += "        ctx.edit_cell(cell.id, disabled=False)\n"
    if operation != "edit":
        code += "        ctx.run_cell(cell.id)\n"
    code += (
        "except RuntimeError as error:\n"
        "    assert 'pending' in str(error), str(error)\n"
        "else:\n"
        "    raise AssertionError('pending edit accepted')\n"
    )
    run_id = await submit(app, notebook_id, code, "rejected")
    assert (await completed(events, run_id))["outcome"] == "succeeded"
    assert next(iter(notebook.document)).config.disabled
    assert not any(
        r.get("event") == "execution"
        and r["data"]["execution"]["cell_id"]
        == next(iter(notebook.document)).id
        and r["data"]["execution"]["run_id"] == run_id
        for r in events.records
    )

    retry = await submit(
        app,
        notebook_id,
        "import marimo._code_mode as cm\n"
        "from marimo._runtime.context import get_context\n"
        "async with cm.get_context() as ctx:\n"
        "    cell = ctx.cells[0]\n"
        "    assert get_context().graph.cells[cell.id].config.disabled\n"
        "    ctx.edit_cell(cell.id, disabled=False)\n"
        "    ctx.run_cell(cell.id)\n"
        "assert not get_context().graph.cells[cell.id].config.disabled\n"
        "assert ctx.globals['x'] == 42\n",
        "retry",
    )
    assert (await completed(events, retry))["outcome"] == "succeeded"
    assert not next(iter(notebook.document)).config.disabled
