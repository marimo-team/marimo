# Copyright 2026 Marimo. All rights reserved.
"""Host API authorization, event streams, and commands."""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

import pytest

from marimo._core import backend as be, protocol
from marimo._core.host import Host
from marimo._core.protocol import ProjectMessage
from marimo._server.host import api as api_module
from marimo._server.host.bridge import SessionBridge
from marimo._server.host.context import HostContext
from marimo._server.host.index import WorkspaceIndex
from marimo._server.main import create_starlette_app
from marimo._server.models.home import MarimoFile
from marimo._server.workspace import FixedFilesWorkspace, SingleFileWorkspace
from tests._core.conftest import ScriptedBackend
from tests._server.host.drive import (
    PORT,
    finished,
    request,
    until_ready,
    wait_for,
)
from tests._server.mocks import (
    get_mock_session_manager,
    get_starlette_server_state_init,
)

if TYPE_CHECKING:
    from starlette.applications import Starlette

TOKEN = "record-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def key(value: str) -> dict[str, str]:
    return {**AUTH, "Idempotency-Key": value}


class Harness:
    def __init__(
        self, app: Starlette, bridge: SessionBridge, root: Path
    ) -> None:
        self.app = app
        self.bridge = bridge
        self.root = root
        self.backends: dict[str, ScriptedBackend] = {}

    @property
    def host(self) -> Host:
        return self.bridge.host

    @property
    def notebook_id(self) -> str:
        (notebook,) = [
            n for n in self.host.notebooks.values() if n.path == "forecasts.py"
        ]
        return notebook.id

    def backend(self) -> ScriptedBackend:
        return self.backends[self.notebook_id]

    async def running(self) -> str:
        """Start a runtime and simulate the backend's running update."""
        response = await finished(
            self.app,
            "PUT",
            f"/notebooks/{self.notebook_id}/runtime",
            headers=key("start"),
            body=b"{}",
        )
        assert response.status == 202, response.body
        self.host.notebook(self.notebook_id).observe(be.Running("0.25.0"))
        return self.notebook_id


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    (tmp_path / "forecasts.py").write_text("import marimo\n")
    workspace = FixedFilesWorkspace(
        [MarimoFile(name="forecasts.py", path=str(tmp_path / "forecasts.py"))],
        directory=str(tmp_path),
    )
    app = create_starlette_app(base_url="", enable_auth=True)
    manager = get_mock_session_manager()
    get_starlette_server_state_init(session_manager=manager).apply(app.state)
    bridge = SessionBridge(manager)
    harness = Harness(app, bridge, tmp_path)

    def make(notebook_id: str) -> ScriptedBackend:
        backend = ScriptedBackend()
        harness.backends[notebook_id] = backend
        return backend

    bridge.index = WorkspaceIndex(bridge.host, workspace, make)
    bridge.index.refresh()
    app.state.host_context = HostContext(
        bridge=bridge,
        token=TOKEN,
        port=PORT,
    )
    return harness


async def test_the_token_the_address_and_the_name_are_all_checked(
    harness: Harness,
) -> None:
    app = harness.app
    assert (await finished(app, "GET", "/events")).status == 401
    assert (
        await finished(
            app, "GET", "/events", headers={"Authorization": "Bearer nope"}
        )
    ).status == 401
    assert (
        await finished(
            app, "GET", "/events", headers=AUTH, client=("10.0.0.5", 1)
        )
    ).status == 403
    assert (
        await finished(
            app, "GET", "/events", headers=AUTH, host="evil.example:1234"
        )
    ).status == 403
    assert (
        await finished(
            app, "GET", "/events", headers=AUTH, host="127.0.0.1:9999"
        )
    ).status == 403
    app.state.host_context = None
    refused = await finished(app, "GET", "/events", headers=AUTH)
    assert refused.status == 404
    assert refused.json()["type"].endswith("/not-found")


async def test_unknown_routes_are_problems(harness: Harness) -> None:
    response = await finished(harness.app, "GET", "/nothing", headers=AUTH)
    assert response.status == 404
    assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.parametrize(
    ("host", "status"),
    [
        ("127.attacker.example:1234", 403),
        ("127.1.2.3:1234", 202),
        ("localhost:1234", 202),
        ("[::1]:1234", 202),
        ("[::ffff:127.0.0.1]:1234", 202),
    ],
)
async def test_only_loopback_names_are_admitted(
    harness: Harness, host: str, status: int
) -> None:
    response = await finished(
        harness.app,
        "PUT",
        f"/notebooks/{harness.notebook_id}/runtime",
        headers=key("start"),
        body=b"{}",
        host=host,
    )
    assert response.status == status


async def test_the_catalog_stream_sends_a_snapshot_then_changes(
    harness: Harness,
) -> None:
    response, _, disconnect = request(
        harness.app, "GET", "/events", headers=AUTH
    )
    await wait_for(response, until_ready)
    assert response.names() == ["host", "project", "notebook", "ready"]
    assert "id" not in response.records[0]
    cursor = int(response.records[-1]["id"])

    notebook = harness.host.notebook(harness.notebook_id)
    notebook.start()
    await wait_for(response, lambda r: r.names()[-1] == "runtime")
    live = response.records[-1]
    assert int(live["id"]) > cursor
    assert live["data"]["runtime"]["status"] == "starting"
    assert "time" in live["data"]
    disconnect()


async def test_catalog_refresh_delivers_updates_on_the_event_loop(
    harness: Harness,
) -> None:
    first, first_task, disconnect_first = request(
        harness.app, "GET", "/events", headers=AUTH
    )
    await wait_for(first, until_ready)
    threads: list[int] = []
    unsubscribe = harness.host.subscribe(
        lambda _: threads.append(threading.get_ident())
    )
    new_file = harness.root / "new.py"
    new_file.write_text("import marimo\n")
    harness.bridge.index._workspace = FixedFilesWorkspace(
        [
            MarimoFile(
                name="forecasts.py", path=str(harness.root / "forecasts.py")
            ),
            MarimoFile(name="new.py", path=str(new_file)),
        ],
        directory=str(harness.root),
    )
    second, second_task, disconnect_second = request(
        harness.app, "GET", "/events", headers=AUTH
    )
    try:
        await wait_for(second, until_ready)
        await wait_for(
            first,
            lambda response: any(
                r.get("data", {}).get("notebook", {}).get("path") == "new.py"
                for r in response.records
            ),
        )
        assert threads
        assert set(threads) == {threading.get_ident()}
    finally:
        unsubscribe()
        disconnect_first()
        disconnect_second()
        await asyncio.gather(first_task, second_task)


async def test_types_and_cursors_apply_to_the_stream(harness: Harness) -> None:
    first, _, disconnect = request(
        harness.app, "GET", "/events", headers=AUTH, query="types=notebook"
    )
    await wait_for(first, until_ready)
    assert first.names() == ["notebook", "ready"]
    cursor = first.records[-1]["id"]
    disconnect()

    harness.host.notebook(harness.notebook_id).start()
    resumed, _, disconnect = request(
        harness.app,
        "GET",
        "/events",
        headers={**AUTH, "Last-Event-ID": cursor},
    )
    await wait_for(resumed, until_ready)
    assert resumed.names() == ["runtime", "ready"]
    disconnect()

    bad = await finished(
        harness.app, "GET", "/events", headers={**AUTH, "Last-Event-ID": "x"}
    )
    assert bad.status == 400


async def test_a_notebook_stream_attaches_the_client(harness: Harness) -> None:
    notebook = harness.host.notebook(harness.notebook_id)
    response, task, disconnect = request(
        harness.app, "GET", f"/notebooks/{notebook.id}/events", headers=AUTH
    )
    await wait_for(response, until_ready)
    assert response.names() == ["notebook", "attachment", "ready"]
    assert response.records[1]["data"]["attachment"]["kind"] == "client"

    disconnect()
    await asyncio.wait_for(task, 5)
    assert [e.name for e in harness.host.events(notebook_id=notebook.id)] == [
        "notebook",
        "ready",
    ]

    missing = await finished(
        harness.app, "GET", "/notebooks/nope/events", headers=AUTH
    )
    assert missing.status == 404


async def test_runtime_lifecycle_over_http(harness: Harness) -> None:
    app, nid = harness.app, harness.notebook_id
    path = f"/notebooks/{nid}/runtime"

    started = await finished(app, "PUT", path, headers=key("k1"), body=b"{}")
    assert started.status == 202
    assert started.json()["status"] == "starting"
    assert harness.backend().calls == [("start", started.json()["id"])]

    again = await finished(app, "PUT", path, headers=key("k2"), body=b"{}")
    assert again.status == 200
    assert again.json()["id"] == started.json()["id"]

    restart = await finished(app, "POST", path + "/restart", headers=key("k3"))
    assert restart.status == 409
    assert restart.json()["type"].endswith("/conflict")

    harness.host.notebook(nid).observe(be.Running("0.25.0"))
    restart = await finished(app, "POST", path + "/restart", headers=key("k4"))
    assert restart.status == 202
    assert restart.json()["status"] == "starting"
    assert restart.json()["id"] != started.json()["id"]

    harness.host.notebook(nid).observe(be.Exited())
    harness.host.notebook(nid).observe(be.Running("0.25.0"))
    stopped = await finished(app, "DELETE", path, headers=key("k5"))
    assert stopped.status == 202
    assert stopped.json()["status"] == "terminating"
    assert stopped.json()["id"] != started.json()["id"]
    assert stopped.json()["id"] == restart.json()["id"]

    harness.host.notebook(nid).observe(be.Exited())
    gone = await finished(app, "DELETE", path, headers=key("k6"))
    assert gone.status == 409
    assert gone.json()["type"].endswith("/no-runtime")


async def test_run_filter_over_http(harness: Harness) -> None:
    nid = await harness.running()
    notebook = harness.host.notebook(nid)
    notebook.run("1", request_id="first")
    notebook.observe(be.Done(protocol.RunId("first"), "succeeded"))
    notebook.run("2", request_id="second")
    response, task, disconnect = request(
        harness.app,
        "GET",
        f"/notebooks/{nid}/events",
        headers=AUTH,
        query="run_id=first",
    )
    try:
        await wait_for(response, until_ready)
        assert response.names() == ["run", "ready"]
        assert response.records[0]["data"]["run"]["id"] == "first"
    finally:
        disconnect()
        await asyncio.wait_for(task, 5)
    invalid = await finished(
        harness.app,
        "GET",
        f"/notebooks/{nid}/events",
        headers=AUTH,
        query="run_id=",
    )
    assert invalid.status == 400


async def test_scratch_runs_over_http(harness: Harness) -> None:
    app, nid = harness.app, harness.notebook_id
    runs = f"/notebooks/{nid}/runtime/runs"
    body = json.dumps({"code": "3 * 3"}).encode()

    refused = await finished(app, "POST", runs, headers=key("r0"), body=body)
    assert refused.status == 409
    assert refused.json()["type"].endswith("/no-runtime")

    await harness.running()
    accepted = await finished(app, "POST", runs, headers=key("r1"), body=body)
    assert accepted.status == 202
    run_id = accepted.json()["id"]
    assert accepted.json()["status"] == "queued"
    assert harness.backend().calls[-1] == ("run", run_id, "3 * 3")

    repeated = await finished(app, "POST", runs, headers=key("r1"), body=body)
    assert repeated.status == 202
    assert repeated.body == accepted.body
    assert harness.backend().calls.count(("run", run_id, "3 * 3")) == 1
    notebook = harness.host.notebook(nid)
    notebook.observe(
        be.Planned(run_id, (be.PlannedExecution("e1", None, "hash", "3 * 3"),))
    )
    notebook.observe(be.Status("e1", "running"))
    running = await finished(app, "POST", runs, headers=key("r1"), body=body)
    assert running.json()["status"] == "running"
    reused = await finished(
        app,
        "POST",
        runs,
        headers=key("r1"),
        body=json.dumps({"code": "4"}).encode(),
    )
    assert reused.status == 409

    busy = await finished(app, "POST", runs, headers=key("r2"), body=body)
    assert busy.status == 409
    assert run_id in busy.json()["detail"]

    interrupted = await finished(
        app, "DELETE", f"{runs}/{run_id}", headers=key("i1")
    )
    assert interrupted.status == 202
    assert harness.backend().calls[-1] == ("interrupt", run_id)

    notebook.observe(be.Concluded("e1", protocol.InterruptedOutcome()))
    notebook.observe(be.Status("e1", "completed"))
    notebook.observe(be.Done(run_id, "interrupted"))
    completed = await finished(app, "POST", runs, headers=key("r1"), body=body)
    assert completed.json()["status"] == "completed"
    assert completed.json()["outcome"] == "interrupted"
    assert completed.json()["completed_at"] is not None
    late = await finished(app, "DELETE", f"{runs}/{run_id}", headers=key("i2"))
    assert late.status == 409
    missing = await finished(app, "DELETE", runs + "/zz", headers=key("i3"))
    assert missing.status == 404

    invalid = await finished(app, "POST", runs, headers=key("r3"), body=b"{}")
    assert invalid.status == 400
    malformed = await finished(app, "POST", runs, headers=key("r4"), body=b"{")
    assert malformed.status == 400
    assert malformed.json()["type"].endswith("/invalid-request")
    unkeyed = await finished(app, "POST", runs, headers=AUTH, body=body)
    assert unkeyed.status == 400


@pytest.mark.parametrize("cancel_waiter", [False, True])
async def test_concurrent_retries_share_the_mutation(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, cancel_waiter: bool
) -> None:
    started, release = asyncio.Event(), asyncio.Event()
    create = harness.bridge.create

    async def delayed_create(
        target: Path, *, name: str | None, request_id: str
    ) -> protocol.Notebook:
        started.set()
        await release.wait()
        return await create(target, name=name, request_id=request_id)

    monkeypatch.setattr(harness.bridge, "create", delayed_create)
    body = json.dumps(
        {"project_id": harness.bridge.index.project_id, "path": "new.py"}
    ).encode()
    first, first_task, _ = request(
        harness.app, "POST", "/notebooks", headers=key("create"), body=body
    )
    await asyncio.wait_for(started.wait(), 5)
    try:
        conflicting = await finished(
            harness.app,
            "POST",
            "/notebooks",
            headers=key("create"),
            body=json.dumps(
                {
                    "project_id": harness.bridge.index.project_id,
                    "path": "other.py",
                }
            ).encode(),
        )
        assert conflicting.status == 409
        if cancel_waiter:
            first_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first_task
        retry, retry_task, _ = request(
            harness.app, "POST", "/notebooks", headers=key("create"), body=body
        )
        # Queue the release after the retry has entered the request handler.
        asyncio.get_running_loop().call_soon(release.set)
        await asyncio.wait_for(retry_task, 5)
        assert retry.status == 201
        if not cancel_waiter:
            await asyncio.wait_for(first_task, 5)
            assert first.body == retry.body
        assert (harness.root / "new.py").exists()
        assert not (harness.root / "other.py").exists()
        assert sorted(n.path for n in harness.host.notebooks.values()) == [
            "forecasts.py",
            "new.py",
        ]
    finally:
        release.set()
        await asyncio.gather(first_task, return_exceptions=True)


async def test_rejected_mutations_do_not_reserve_the_key(
    harness: Harness,
) -> None:
    path = f"/notebooks/{harness.notebook_id}"
    rejected = await finished(
        harness.app,
        "PATCH",
        path,
        headers=key("move"),
        body=b'{"path":"forecasts.py"}',
    )
    assert rejected.status == 409
    corrected = await finished(
        harness.app,
        "PATCH",
        path,
        headers=key("move"),
        body=b'{"path":"corrected.py"}',
    )
    assert corrected.status == 200
    assert corrected.json()["path"] == "corrected.py"
    assert (harness.root / "corrected.py").exists()
    assert not (harness.root / "forecasts.py").exists()


async def test_create_update_and_delete_notebooks(harness: Harness) -> None:
    app, root = harness.app, harness.root
    project = harness.bridge.index.project_id

    created = await finished(
        app,
        "POST",
        "/notebooks",
        headers=key("c1"),
        body=json.dumps(
            {"project_id": project, "path": "new/one.py"}
        ).encode(),
    )
    assert created.status == 201, created.body
    record = created.json()
    assert record["path"] == str(Path("new") / "one.py")
    assert record["name"] == "one"
    assert (root / "new" / "one.py").read_text().startswith("import marimo")
    assert record["id"] in harness.host.notebooks

    again = await finished(
        app,
        "POST",
        "/notebooks",
        headers=key("c2"),
        body=json.dumps(
            {"project_id": project, "path": "new/one.py"}
        ).encode(),
    )
    assert again.status == 409
    escaped = await finished(
        app,
        "POST",
        "/notebooks",
        headers=key("c3"),
        body=json.dumps({"project_id": project, "path": "../x.py"}).encode(),
    )
    assert escaped.status == 400
    elsewhere = await finished(
        app,
        "POST",
        "/notebooks",
        headers=key("c4"),
        body=json.dumps({"project_id": "nope", "path": "y.py"}).encode(),
    )
    assert elsewhere.status == 404

    moved = await finished(
        app,
        "PATCH",
        f"/notebooks/{record['id']}",
        headers=key("u1"),
        body=json.dumps({"path": "two.py", "name": "Two"}).encode(),
    )
    assert moved.status == 200, moved.body
    assert moved.json()["path"] == "two.py"
    assert moved.json()["name"] == "Two"
    assert (root / "two.py").exists()
    assert not (root / "new" / "one.py").exists()
    harness.bridge.index.refresh()
    assert harness.host.notebooks[record["id"]].name == "Two"

    onto = await finished(
        app,
        "PATCH",
        f"/notebooks/{record['id']}",
        headers=key("u2"),
        body=json.dumps({"path": "forecasts.py"}).encode(),
    )
    assert onto.status == 409

    deleted = await finished(
        app, "DELETE", f"/notebooks/{record['id']}", headers=key("d1")
    )
    assert deleted.status == 204
    assert not (root / "two.py").exists()
    assert record["id"] not in harness.host.notebooks

    repeated = await finished(
        app, "DELETE", f"/notebooks/{record['id']}", headers=key("d1")
    )
    assert repeated.status == 204
    assert repeated.body == deleted.body == b""

    await harness.running()
    busy = await finished(
        app, "DELETE", f"/notebooks/{harness.notebook_id}", headers=key("d2")
    )
    assert busy.status == 409


async def test_open_selects_the_notebook_outside_the_working_directory(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    file = harness.root / "forecasts.py"
    workspace = SingleFileWorkspace(MarimoFile(name=file.name, path=str(file)))
    harness.app.state.session_manager.workspace = workspace
    launch = harness.root / "launch"
    launch.mkdir()
    (launch / file.name).write_text("another notebook")
    monkeypatch.chdir(launch)
    opened: list[str] = []
    ready = threading.Event()

    def open_browser(_browser: str, url: str) -> None:
        opened.append(url)
        ready.set()

    monkeypatch.setattr(api_module, "open_url_in_browser", open_browser)
    response = await finished(
        harness.app,
        "POST",
        f"/notebooks/{harness.notebook_id}/open",
        headers=key("o1"),
    )

    assert response.status == 200
    url = response.json()["url"]
    query = parse_qs(urlsplit(url).query)
    assert workspace.resolve(query["file"][0]) == str(file)
    assert query["access_token"] == ["fake-token"]
    assert TOKEN not in url
    assert await asyncio.to_thread(ready.wait, 5)
    assert opened == [url]


async def test_operations_the_host_does_not_offer_are_501(
    harness: Harness,
) -> None:
    notebook = harness.host.notebook(harness.notebook_id)
    host = Host(operations=[])
    [project] = [
        e.data.project
        for e in harness.host.events()
        if isinstance(e.data, ProjectMessage)
    ]
    host.update_project(project)
    host.add_notebook(harness.host.notebooks[notebook.id], harness.backend())
    harness.bridge.host = host
    response = await finished(
        harness.app,
        "PUT",
        f"/notebooks/{notebook.id}/runtime",
        headers=key("x1"),
    )
    assert response.status == 501
    assert response.json()["type"].endswith("/unsupported-operation")


async def test_competing_moves_preserve_both_notebooks(
    harness: Harness,
) -> None:
    first = harness.root / "forecasts.py"
    second = harness.root / "second.py"
    first.write_text("first notebook")
    second.write_text("second notebook")
    other = harness.bridge.index.ensure(str(second))
    assert other is not None
    ids = [harness.notebook_id, other.id]

    responses = await asyncio.gather(
        *(
            finished(
                harness.app,
                "PATCH",
                f"/notebooks/{nid}",
                headers=key(f"move-{i}"),
                body=b'{"path":"destination.py"}',
            )
            for i, nid in enumerate(ids)
        )
    )

    assert sorted(r.status for r in responses) == [200, 409]
    records = [harness.host.notebooks[nid] for nid in ids]
    assert len({record.path for record in records}) == 2
    assert {
        (harness.root / record.path).read_text()
        for record in records
        if record.path is not None
    } == {"first notebook", "second notebook"}


@pytest.mark.parametrize("operation", ["create", "move"])
async def test_symlink_escape_has_no_filesystem_side_effects(
    harness: Harness, tmp_path: Path, operation: str
) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (harness.root / "link").symlink_to(outside, target_is_directory=True)
    source = harness.root / "forecasts.py"
    original = source.read_text()
    if operation == "create":
        response = await finished(
            harness.app,
            "POST",
            "/notebooks",
            headers=key("escape"),
            body=json.dumps(
                {
                    "project_id": harness.bridge.index.project_id,
                    "path": "link/nested/new.py",
                }
            ).encode(),
        )
    else:
        response = await finished(
            harness.app,
            "PATCH",
            f"/notebooks/{harness.notebook_id}",
            headers=key("escape"),
            body=b'{"path":"link/nested/new.py"}',
        )
    assert response.status == 409
    assert list(outside.iterdir()) == []
    assert source.read_text() == original
    assert [n.path for n in harness.host.notebooks.values()] == [
        "forecasts.py"
    ]
