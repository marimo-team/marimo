# Copyright 2026 Marimo. All rights reserved.
"""Host commands executed by real sessions and kernels."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import TYPE_CHECKING, Any

import pytest

from marimo._core.document import code_hash
from marimo._server.host.bridge import SessionBridge
from marimo._server.host.context import HostContext
from marimo._server.main import create_starlette_app
from marimo._server.workspace import SingleFileWorkspace
from marimo._session.notebook import AppFileManager
from marimo._session.requests import InstantiateNotebookRequest
from marimo._utils.marimo_path import MarimoPath
from tests._server.host.drive import PORT, finished, request, wait_for
from tests._server.mocks import (
    get_mock_session_manager,
    get_starlette_server_state_init,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from starlette.applications import Starlette

    from tests._server.host.drive import Response

AUTH = {"Authorization": "Bearer execution-test"}


def key(value: str) -> dict[str, str]:
    return {**AUTH, "Idempotency-Key": value}


@pytest.fixture
def notebook_source(request: pytest.FixtureRequest) -> str:
    return getattr(
        request,
        "param",
        (
            "import marimo\napp = marimo.App()\n"
            "@app.cell\ndef _():\n    example = 7\n    return (example,)\n"
        ),
    )


@pytest.fixture
async def live_host(
    tmp_path: Path,
    notebook_source: str,
) -> AsyncIterator[tuple[Starlette, str, Response]]:
    manager = get_mock_session_manager()
    file = tmp_path / "notebook.py"
    file.write_text(notebook_source)
    manager.workspace = SingleFileWorkspace.from_path(MarimoPath(file))
    manager.redirect_console_to_browser = True
    app = create_starlette_app(base_url="", enable_auth=True)
    get_starlette_server_state_init(session_manager=manager).apply(app.state)
    bridge = SessionBridge(manager)
    await bridge.open()
    app.state.host_context = HostContext(
        bridge=bridge, token="execution-test", port=PORT
    )
    notebook = next(iter(bridge.host.notebooks.values()))
    events, task, disconnect = request(
        app, "GET", f"/notebooks/{notebook.id}/events", headers=AUTH
    )
    try:
        started = await finished(
            app,
            "PUT",
            f"/notebooks/{notebook.id}/runtime",
            headers=key("start"),
        )
        assert started.status == 202
        await wait_for(
            events,
            lambda response: any(
                r.get("data", {}).get("runtime", {}).get("status") == "running"
                for r in response.records
            ),
            timeout=15,
        )
        yield app, notebook.id, events
    finally:
        disconnect()
        await asyncio.wait_for(task, 5)
        bridge.close()
        await manager.shutdown()


async def test_move_preserves_the_running_notebook(
    live_host: tuple[Starlette, str, Response], tmp_path: Path
) -> None:
    app, notebook_id, events = live_host
    host = app.state.host_context.bridge.host
    runtime = (await host.notebook(notebook_id)).runtime
    source, target = tmp_path / "notebook.py", tmp_path / "moved.py"
    session = next(iter(app.state.session_manager.sessions.values()))
    cells = list(session.app_file_manager.app.cell_manager.codes())

    moved = await finished(
        app,
        "PATCH",
        f"/notebooks/{notebook_id}",
        headers=key("move"),
        body=b'{"path":"moved.py"}',
    )
    assert moved.status == 200
    assert (moved.json()["id"], moved.json()["path"]) == (
        notebook_id,
        "moved.py",
    )
    assert not source.exists()
    assert list(AppFileManager(str(target)).app.cell_manager.codes()) == cells
    assert session.app_file_manager.path == str(target)
    assert (await host.notebook(notebook_id)).runtime == runtime

    accepted = await finished(
        app,
        "POST",
        f"/notebooks/{notebook_id}/runtime/runs",
        headers=key("after-move"),
        body=b'{"code":"6 * 7"}',
    )
    assert accepted.status == 202
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("status") == "completed"
            for r in response.records
        ),
    )
    [outcome] = [
        r["data"]["execution"]["outcome"]
        for r in events.records
        if r.get("data", {}).get("execution", {}).get("status") == "completed"
    ]
    assert outcome == {
        "kind": "value",
        "display": {
            "mimetype": "text/html",
            "data": "<pre class='text-xs'>42</pre>",
        },
    }


async def test_saving_keeps_an_edit_made_while_the_file_is_written(
    live_host: tuple[Starlette, str, Response],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, notebook_id, events = live_host
    document = (await app.state.host_context.bridge.host.notebook(notebook_id)).document
    assert document is not None
    cell = next(
        r["data"]["cell"] for r in events.records if r.get("event") == "cell"
    )
    session = next(iter(app.state.session_manager.sessions.values()))
    started = asyncio.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()
    original_save = AppFileManager.save_from_cells

    def save(manager: AppFileManager, cells: Any) -> str:
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5)
        return original_save(manager, cells)

    monkeypatch.setattr(AppFileManager, "save_from_cells", save)
    saved, task, _ = request(
        app,
        "POST",
        f"/notebooks/{notebook_id}/save",
        headers=key("save"),
        body=b"{}",
    )
    try:
        await asyncio.wait_for(started.wait(), 5)
        edited = await finished(
            app,
            "POST",
            f"/notebooks/{notebook_id}/edits",
            headers=key("edit-during-save"),
            body=json.dumps(
                {
                    "changes": [
                        {
                            "kind": "put_cell",
                            "base_etag": cell["etag"],
                            "cell": {"id": cell["id"], "code": "example = 8"},
                        }
                    ]
                }
            ).encode(),
        )
        assert edited.status == 200, edited.body
    finally:
        release.set()
        await asyncio.wait_for(task, 5)

    # The file has the snapshot; the editor and the host keep the edit.
    assert saved.status == 200, saved.body
    assert "example = 7" in (tmp_path / "notebook.py").read_text()
    assert [c.code for c in session.document.cells] == ["example = 8"]
    assert [c.code for c in document] == ["example = 8"]
    assert document._record.saved_etag != document._record.etag


@pytest.mark.parametrize(
    ("code", "kind", "name", "value"),
    [
        (
            "print('hello')\nimport marimo as mo\nmo.Html('<b>9</b>')",
            "value",
            None,
            "<b>9</b>",
        ),
        ("", "value", None, None),
        ("if !!!", "error", None, None),
        ("1 / 0", "error", "ZeroDivisionError", None),
        ("input('hello')", "error", "EOFError", None),
    ],
)
async def test_scratch_outcomes_from_the_kernel(
    live_host: tuple[Starlette, str, Response],
    code: str,
    kind: str,
    name: str | None,
    value: str | None,
) -> None:
    app, notebook_id, events = live_host
    accepted = await finished(
        app,
        "POST",
        f"/notebooks/{notebook_id}/runtime/runs",
        headers=key("run"),
        body=json.dumps({"code": code}).encode(),
    )
    assert accepted.status == 202
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("status") == "completed"
            for r in response.records
        ),
    )
    [execution] = [
        r["data"]["execution"]
        for r in events.records
        if r.get("data", {}).get("execution", {}).get("status") == "completed"
    ]
    outcome = execution["outcome"]
    assert execution["code"] == code
    assert execution["code_hash"]
    assert execution["runtime_id"] is not None
    assert execution["caused_by"] is None
    if kind == "value":
        assert outcome == {
            "kind": "value",
            "display": None
            if value is None
            else {"mimetype": "text/html", "data": value},
        }
        if value is not None:
            assert "hello\n" == "".join(
                r["data"]["console"]["text"]
                for r in events.records
                if r.get("event") == "console"
            )
    else:
        assert (
            outcome["kind"],
            outcome["error"]["kind"],
            outcome["error"]["name"],
        ) == ("error", "syntax" if name is None else "exception", name)
        assert outcome["error"]["message"]


async def test_background_output_after_a_scratch_run_is_dropped(
    live_host: tuple[Starlette, str, Response],
) -> None:
    """A completed scratch run is history; the backend forgets it.

    Output its code produces later, from a background thread, has no
    current execution to join and never reaches clients.
    """
    app, notebook_id, events = live_host
    path = f"/notebooks/{notebook_id}/runtime/runs"
    code = """import builtins
import threading
import marimo as mo
builtins._host_test_gate = threading.Event()
builtins._host_test_printed = threading.Event()
def worker():
    builtins._host_test_gate.wait(5)
    print("late output")
    builtins._host_test_printed.set()
mo.Thread(target=worker).start()
"""
    first = await finished(
        app,
        "POST",
        path,
        headers=key("first"),
        body=json.dumps({"code": code}).encode(),
    )
    assert first.status == 202
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("id") == first.json()["id"]
            and r["data"]["run"]["status"] == "completed"
            for r in response.records
        ),
    )
    second = await finished(
        app,
        "POST",
        path,
        headers=key("second"),
        body=json.dumps(
            {
                "code": "import builtins\nbuiltins._host_test_gate.set()\nassert builtins._host_test_printed.wait(5)\ndel builtins._host_test_gate, builtins._host_test_printed"
            }
        ).encode(),
    )
    assert second.status == 202
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("id") == second.json()["id"]
            and r["data"]["run"]["status"] == "completed"
            for r in response.records
        ),
    )
    assert (
        next(
            r["data"]["run"]["outcome"]
            for r in reversed(events.records)
            if r.get("data", {}).get("run", {}).get("id")
            == second.json()["id"]
        )
        == "succeeded"
    )
    console = [
        r["data"]["console"]
        for r in events.records
        if r.get("event") == "console"
    ]
    assert not any("late output" in item["text"] for item in console)


async def test_queued_cancellation_never_executes_the_code(
    live_host: tuple[Starlette, str, Response], tmp_path: Path
) -> None:
    app, notebook_id, events = live_host
    session = next(iter(app.state.session_manager.sessions.values()))
    marker = tmp_path / "executed"
    runs = f"/notebooks/{notebook_id}/runtime/runs"
    async with session.scratchpad_lock:
        accepted = await finished(
            app,
            "POST",
            runs,
            headers=key("canceled"),
            body=json.dumps(
                {
                    "code": f"__import__('pathlib').Path({str(marker)!r}).touch()"
                }
            ).encode(),
        )
        assert accepted.status == 202
        interrupted = await finished(
            app,
            "DELETE",
            runs + "/" + accepted.json()["id"],
            headers=key("interrupt"),
        )
        assert interrupted.status == 202
        await wait_for(
            events,
            lambda response: any(
                r.get("data", {}).get("run", {}).get("status") == "completed"
                for r in response.records
            ),
        )
    [outcome] = [
        r["data"]["execution"]["outcome"]
        for r in events.records
        if r.get("data", {}).get("execution", {}).get("status") == "completed"
    ]
    assert outcome == {"kind": "interrupted"}
    following = await finished(
        app, "POST", runs, headers=key("next"), body=b'{"code":"42"}'
    )
    assert following.status == 202
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("id")
            == following.json()["id"]
            and r["data"]["run"]["status"] == "completed"
            for r in response.records
        ),
    )
    assert not marker.exists()


async def test_run_retries_return_the_result_even_after_restart(
    live_host: tuple[Starlette, str, Response], tmp_path: Path
) -> None:
    app, notebook_id, events = live_host
    runtime = f"/notebooks/{notebook_id}/runtime"
    runs = runtime + "/runs"
    marker = tmp_path / "executions"
    body = json.dumps(
        {
            "code": (
                f"_marker = __import__('pathlib').Path({str(marker)!r})\n"
                "_marker.write_text((_marker.read_text() if _marker.exists() else '') + 'x')"
            )
        }
    ).encode()
    accepted = await finished(
        app, "POST", runs, headers=key("once"), body=body
    )
    assert accepted.status == 202
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("status") == "completed"
            for r in response.records
        ),
    )
    [completed] = [
        r["data"]["run"]
        for r in events.records
        if r.get("data", {}).get("run", {}).get("status") == "completed"
    ]
    replayed = await finished(
        app, "POST", runs, headers=key("once"), body=body
    )
    assert replayed.status == 202
    assert replayed.json() == completed

    restarted = await finished(
        app, "POST", runtime + "/restart", headers=key("restart")
    )
    assert restarted.status == 202
    new_runtime_id = restarted.json()["id"]
    assert restarted.json()["status"] == "starting"
    await wait_for(
        events,
        lambda response: any(
            r.get("event") == "runtime"
            and r["data"]["runtime"]["id"] == new_runtime_id
            and r["data"]["runtime"]["status"] == "running"
            for r in response.records
        ),
        timeout=15,
    )
    replayed = await finished(
        app, "POST", runs, headers=key("once"), body=body
    )
    assert replayed.status == 202
    assert replayed.json() == completed
    assert marker.read_text() == "x"


CASCADE_NOTEBOOK = """import marimo
app = marimo.App()

@app.cell
def _():
    import anywidget
    import traitlets
    import threading
    import marimo as mo
    class CounterWidget(anywidget.AnyWidget):
        value = traitlets.Int(0).tag(sync=True)
    counter = CounterWidget()
    get_x, set_x = mo.state(counter.value)
    counter.observe(lambda _: set_x(counter.value), names="value")
    gate = threading.Event()
    return counter, get_x, set_x, gate, mo

@app.cell
def _(mo):
    get_y, set_y = mo.state(0)
    return get_y, set_y

@app.cell
def _(get_x, set_y):
    current = get_x()
    if current == 99:
        raise ValueError("downstream failed")
    set_y(current)
    return

@app.cell
def _(get_y):
    print(10 + get_y())
    return
"""


async def initialize_cascade(app: Starlette, events: Response) -> None:
    # Pytest can import the test directory as an empty namespace package.
    if not hasattr(pytest.importorskip("anywidget"), "AnyWidget"):
        pytest.skip("requires anywidget")
    session = next(iter(app.state.session_manager.sessions.values()))
    session.instantiate(
        InstantiateNotebookRequest(object_ids=[], values=[], auto_run=True),
        http_request=None,
    )
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("status") == "completed"
            for r in response.records
        ),
    )
    runs = [
        r["data"]["run"] for r in events.records if r.get("event") == "run"
    ]
    assert runs[-1]["outcome"] == "succeeded", [
        r["data"]["execution"]["outcome"]
        for r in events.records
        if r.get("event") == "execution"
        and r["data"]["execution"]["status"] == "completed"
    ]


@pytest.mark.requires("anywidget", "traitlets")
@pytest.mark.parametrize(
    "notebook_source", [CASCADE_NOTEBOOK], indirect=True, ids=["widget"]
)
@pytest.mark.parametrize(
    ("value", "outcome", "children"), [(20, "succeeded", 2), (99, "failed", 1)]
)
async def test_scratch_run_includes_the_full_reactive_cycle(
    live_host: tuple[Starlette, str, Response],
    value: int,
    outcome: str,
    children: int,
) -> None:
    app, notebook_id, events = live_host
    await initialize_cascade(app, events)
    accepted = await finished(
        app,
        "POST",
        f"/notebooks/{notebook_id}/runtime/runs",
        headers=key("cascade"),
        body=json.dumps({"code": f"counter.value = {value}"}).encode(),
    )
    assert accepted.status == 202
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("id") == accepted.json()["id"]
            and r["data"]["run"]["status"] == "completed"
            for r in response.records
        ),
    )
    records = [
        r
        for r in events.records
        if r.get("data", {}).get("request_id") == "cascade"
    ]
    assert records[-1]["event"] == "run"
    assert records[-1]["data"]["run"]["outcome"] == outcome
    executions = [
        r["data"]["execution"]
        for r in records
        if r["event"] == "execution"
        and r["data"]["execution"]["status"] == "completed"
    ]
    assert len(executions) == children + 1
    root, *downstream = executions
    assert root["cell_id"] is None
    assert root["outcome"]["kind"] == "value"
    assert all(
        e["run_id"] == accepted.json()["id"]
        and e["cell_id"] is not None
        and e["caused_by"] == root["id"]
        for e in downstream
    )
    assert downstream[-1]["outcome"]["kind"] == (
        "error" if outcome == "failed" else "value"
    )
    if outcome == "succeeded":
        consoles = [
            r["data"]["console"] for r in records if r["event"] == "console"
        ]
        assert "".join(c["text"] for c in consoles) == "30\n"
        assert {c["execution_id"] for c in consoles} == {downstream[-1]["id"]}


@pytest.mark.requires("anywidget", "traitlets")
@pytest.mark.parametrize(
    "notebook_source", [CASCADE_NOTEBOOK], indirect=True, ids=["widget"]
)
@pytest.mark.parametrize("command", [False, True])
async def test_detached_reactivity_starts_a_new_run(
    live_host: tuple[Starlette, str, Response],
    command: bool,
) -> None:
    app, notebook_id, events = live_host
    await initialize_cascade(app, events)
    origin = (
        "import asyncio\n"
        "import marimo._code_mode as cm\n"
        "from marimo._runtime.commands import ExecuteCellsCommand\n"
        "ctx = cm.get_context()\n"
        "async def later():\n"
        "    await asyncio.to_thread(gate.wait)\n"
        "    await ctx.execute_command(ExecuteCellsCommand(cell_ids=['later'], codes=['print(30)']))\n"
        "asyncio.create_task(later())"
        if command
        else "mo.Thread(target=lambda: (gate.wait(), set_x(20))).start()"
    )
    submitted = {}
    for request_id, code in [
        ("origin", origin),
        ("release", "gate.set()"),
    ]:
        accepted = await finished(
            app,
            "POST",
            f"/notebooks/{notebook_id}/runtime/runs",
            headers=key(request_id),
            body=json.dumps({"code": code}).encode(),
        )
        assert accepted.status == 202
        run_id = accepted.json()["id"]
        submitted[request_id] = run_id
        await wait_for(
            events,
            lambda response, run_id=run_id: any(
                r.get("data", {}).get("run", {}).get("id") == run_id
                and r["data"]["run"]["status"] == "completed"
                for r in response.records
            ),
        )
    await wait_for(
        events,
        lambda response: any(
            "30\n" in r.get("data", {}).get("console", {}).get("text", "")
            for r in response.records
        ),
    )
    printed = next(
        r["data"]["console"]
        for r in events.records
        if "30\n" in r.get("data", {}).get("console", {}).get("text", "")
    )
    execution = next(
        r["data"]["execution"]
        for r in events.records
        if r.get("data", {}).get("execution", {}).get("id")
        == printed["execution_id"]
    )
    assert execution["run_id"] not in submitted.values()
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("id") == execution["run_id"]
            and r["data"]["run"]["status"] == "completed"
            for r in response.records
        ),
    )
    origin = [
        r["data"]["run"]
        for r in events.records
        if r.get("data", {}).get("run", {}).get("id") == submitted["origin"]
    ]
    assert [r["status"] for r in origin] == ["queued", "running", "completed"]
    assert origin[-1]["outcome"] == "succeeded"


async def test_nested_evaluations_keep_the_scratch_result_and_skipped_child(
    live_host: tuple[Starlette, str, Response],
) -> None:
    app, notebook_id, events = live_host
    code = (
        "import marimo._code_mode as cm\n"
        "async with cm.get_context() as ctx:\n"
        "    a = ctx.create_cell('x = 1/0')\n"
        "    b = ctx.create_cell('y = x + 1')\n"
        "    ctx.run_cell(a)\n"
        "    ctx.run_cell(b)\n"
        "42"
    )
    accepted = await finished(
        app,
        "POST",
        f"/notebooks/{notebook_id}/runtime/runs",
        headers=key("nested"),
        body=json.dumps({"code": code}).encode(),
    )
    assert accepted.status == 202
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("id") == accepted.json()["id"]
            and r["data"]["run"]["status"] == "completed"
            for r in response.records
        ),
    )
    records = [
        r
        for r in events.records
        if r.get("data", {}).get("request_id") == "nested"
    ]
    assert records[-1]["data"]["run"]["outcome"] == "failed"
    executions = [
        r["data"]["execution"]
        for r in records
        if r["event"] == "execution"
        and r["data"]["execution"]["status"] == "completed"
    ]
    assert len(executions) == 3
    [root] = [e for e in executions if e["cell_id"] is None]
    assert root["outcome"]["kind"] == "value"
    assert "42" in root["outcome"]["display"]["data"]
    assert all(
        e["outcome"]["kind"] == "error"
        for e in executions
        if e["cell_id"] is not None
    )


async def test_a_fixed_cell_replaces_its_failed_compilation(
    live_host: tuple[Starlette, str, Response],
) -> None:
    app, notebook_id, events = live_host
    code = (
        "import marimo._code_mode as cm\n"
        "from marimo._runtime.commands import ExecuteCellsCommand\n"
        "await cm.get_context().execute_command(ExecuteCellsCommand(cell_ids=['child'], codes=['if !!!']))\n"
        "await cm.get_context().execute_command(ExecuteCellsCommand(cell_ids=['child'], codes=['x = 42']))\n"
        "42"
    )
    accepted = await finished(
        app,
        "POST",
        f"/notebooks/{notebook_id}/runtime/runs",
        headers=key("retry"),
        body=json.dumps({"code": code}).encode(),
    )
    assert accepted.status == 202
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("id") == accepted.json()["id"]
            and r["data"]["run"]["status"] == "completed"
            for r in response.records
        ),
    )
    executions = [
        r["data"]["execution"]
        for r in events.records
        if r.get("data", {}).get("execution", {}).get("cell_id") == "child"
        and r["data"]["execution"]["status"] == "completed"
    ]
    assert [(e["code_hash"], e["outcome"]["kind"]) for e in executions] == [
        (code_hash("if !!!"), "error"),
        (code_hash("x = 42"), "value"),
    ]
    assert len({e["id"] for e in executions}) == 2
    runs = [
        r["data"]["run"]
        for r in events.records
        if r.get("data", {}).get("run", {}).get("id") == accepted.json()["id"]
    ]
    assert runs[-1]["outcome"] == "failed"


async def test_nested_commands_can_run_a_cell_queued_by_the_outer_command(
    live_host: tuple[Starlette, str, Response],
) -> None:
    app, notebook_id, events = live_host
    inner = (
        "x = 42\n"
        "import marimo._code_mode as cm\n"
        "from marimo._runtime.commands import ExecuteCellsCommand\n"
        "await cm.get_context().execute_command(ExecuteCellsCommand("
        "cell_ids=['b'], codes=['print(x)']))"
    )
    code = (
        "import marimo._code_mode as cm\n"
        "from marimo._runtime.commands import ExecuteCellsCommand\n"
        "await cm.get_context().execute_command(ExecuteCellsCommand("
        f"cell_ids=['a', 'b'], codes=[{inner!r}, 'print(x)']))"
    )
    accepted = await finished(
        app,
        "POST",
        f"/notebooks/{notebook_id}/runtime/runs",
        headers=key("nested-queue"),
        body=json.dumps({"code": code}).encode(),
    )
    assert accepted.status == 202
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("id") == accepted.json()["id"]
            and r["data"]["run"]["status"] == "completed"
            for r in response.records
        ),
    )
    executions = [
        r["data"]["execution"]
        for r in events.records
        if r.get("data", {}).get("execution", {}).get("cell_id") == "b"
        and r["data"]["execution"]["status"] == "completed"
    ]
    assert [e["outcome"]["kind"] for e in executions] == ["value", "value"]
    assert len({e["id"] for e in executions}) == 2
    runs = [
        r["data"]["run"]
        for r in events.records
        if r.get("data", {}).get("run", {}).get("id") == accepted.json()["id"]
    ]
    assert runs[-1]["outcome"] == "succeeded"


@pytest.mark.parametrize("nested_scratch", [False, True])
@pytest.mark.parametrize("child_code", ["1/0", "if !!!"])
async def test_awaited_commands_join_the_enclosing_run(
    live_host: tuple[Starlette, str, Response],
    nested_scratch: bool,
    child_code: str,
) -> None:
    app, notebook_id, events = live_host
    command = (
        f"ExecuteScratchpadCommand(code={child_code!r}, request=None)"
        if nested_scratch
        else f"ExecuteCellsCommand(cell_ids=['child'], codes=[{child_code!r}])"
    )
    sibling = (
        "await cm.get_context().execute_command(ExecuteScratchpadCommand(code='3 * 3', request=None))\n"
        if nested_scratch
        else ""
    )
    code = (
        "import marimo._code_mode as cm\n"
        "from marimo._runtime.commands import ExecuteCellsCommand, ExecuteScratchpadCommand\n"
        f"await cm.get_context().execute_command({command})\n{sibling}42"
    )
    before = len(events.records)
    accepted = await finished(
        app,
        "POST",
        f"/notebooks/{notebook_id}/runtime/runs",
        headers=key("awaited"),
        body=json.dumps({"code": code}).encode(),
    )
    assert accepted.status == 202
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("id") == accepted.json()["id"]
            and r["data"]["run"]["status"] == "completed"
            for r in response.records
        ),
    )
    records = events.records[before:]
    runs = [r["data"]["run"] for r in records if r.get("event") == "run"]
    assert {r["id"] for r in runs} == {accepted.json()["id"]}
    assert runs[-1]["outcome"] == "failed"
    executions = [
        r["data"]["execution"]
        for r in records
        if r.get("event") == "execution"
        and r["data"]["execution"]["status"] == "completed"
    ]
    assert len(executions) == (3 if nested_scratch else 2)
    [root] = [e for e in executions if e["caused_by"] is None]
    children = [e for e in executions if e["caused_by"] == root["id"]]
    assert len(children) == len(executions) - 1
    child = children[0]
    assert root["outcome"]["kind"] == "value"
    assert "42" in root["outcome"]["display"]["data"]
    assert child["outcome"]["kind"] == "error"
    assert child["code_hash"] == code_hash(child_code)
    assert all(e["run_id"] == accepted.json()["id"] for e in executions)


@pytest.mark.parametrize(
    "notebook_source",
    [
        "import marimo\napp = marimo.App()\n@app.cell\ndef _():\n    x = __file__\n    return (x,)\n"
    ],
    indirect=True,
)
async def test_rename_reactivity_completes_its_run(
    live_host: tuple[Starlette, str, Response],
) -> None:
    app, notebook_id, events = live_host
    session = next(iter(app.state.session_manager.sessions.values()))
    session.instantiate(
        InstantiateNotebookRequest(object_ids=[], values=[], auto_run=True),
        http_request=None,
    )
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("status") == "completed"
            for r in response.records
        ),
    )
    before = len(events.records)
    moved = await finished(
        app,
        "PATCH",
        f"/notebooks/{notebook_id}",
        headers=key("rename"),
        body=b'{"path":"renamed.py"}',
    )
    assert moved.status == 200
    await wait_for(
        events,
        lambda response: any(
            r.get("data", {}).get("run", {}).get("status") == "completed"
            for r in response.records[before:]
        ),
    )
    runs = [
        r["data"]["run"]
        for r in events.records[before:]
        if r.get("event") == "run"
    ]
    assert runs[-1]["outcome"] == "succeeded"
    accepted = await finished(
        app,
        "POST",
        f"/notebooks/{notebook_id}/runtime/runs",
        headers=key("after-rename"),
        body=b'{"code":"42"}',
    )
    assert accepted.status == 202
