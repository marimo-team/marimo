# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from marimo._host.host import Host
from marimo._host.model import HostState, Indexed, Notebook, Project
from marimo._host.transitions import Action, KernelReady
from marimo._server.host.context import HOST_API_PATH, HostContext
from marimo._server.host.lifespan import OPERATIONS
from marimo._server.main import create_starlette_app
from marimo._types.ids import NotebookId, ProjectId, RuntimeId
from tests._server.host.drive import (
    AUTHORITY,
    PORT,
    finished,
    request,
    wait_for,
)
from tests._server.mocks import get_starlette_server_state_init

if TYPE_CHECKING:
    from collections.abc import Iterator

    from starlette.applications import Starlette

TOKEN = "record-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
NOW = datetime(2026, 10, 1, 9, 14, 2, tzinfo=timezone.utc)
PROJECT = ProjectId("proj-1")
NOTEBOOK = NotebookId("nb-1")


class FakeRuntime:
    def __init__(self) -> None:
        self.performed: list[Action] = []
        self.sandbox = False

    def perform(self, action: Action) -> None:
        self.performed.append(action)

    def session_for(self, runtime_id: RuntimeId) -> None:
        del runtime_id
        return


class NoIndex:
    """Stands in for the workspace index; the state is built by hand."""

    root = Path("/p")
    project_id = PROJECT

    def refresh(self) -> None:
        pass

    async def refresh_in_thread(self) -> None:
        pass

    def ensure(self, path: str, *, request_id: str | None = None) -> None:
        del path, request_id


def make_app() -> tuple[Starlette, Host, FakeRuntime]:
    app = create_starlette_app(base_url="", enable_auth=True)
    get_starlette_server_state_init().apply(app.state)
    runtime = FakeRuntime()
    state = (
        HostState()
        .with_project(Project(PROJECT, "forecasting", Path("/p"), Indexed()))
        .with_notebook(
            Notebook(NOTEBOOK, PROJECT, "forecasts", Path("forecasts.py"), NOW)
        )
    )
    host = Host(state, runtime, operations=OPERATIONS)
    app.state.host_context = HostContext(
        host=host,
        runtime=runtime,  # type: ignore[arg-type]
        index=NoIndex(),  # type: ignore[arg-type]
        token=TOKEN,
        url=f"http://{AUTHORITY}{HOST_API_PATH}",
        port=PORT,
    )
    return app, host, runtime


@pytest.fixture
def app() -> Starlette:
    return make_app()[0]


@pytest.fixture
def client(app: Starlette) -> Iterator[TestClient]:
    with TestClient(
        app, base_url=f"http://{AUTHORITY}", client=("127.0.0.1", 50000)
    ) as client:
        yield client


def host_of(app: Starlette) -> Host:
    return app.state.host_context.host  # type: ignore[no-any-return]


def url(path: str) -> str:
    return HOST_API_PATH + path


def key(value: str) -> dict[str, str]:
    return {**AUTH, "Idempotency-Key": value}


def runtime_path() -> str:
    return url(f"/notebooks/{NOTEBOOK}/runtime")


# Who may call


def test_requests_without_the_record_token_are_refused(
    client: TestClient,
) -> None:
    response = client.delete(runtime_path())
    assert response.status_code == 401
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    problem = response.json()
    assert problem["type"].endswith("/unauthorized")
    assert problem["status"] == 401

    wrong = client.delete(
        runtime_path(), headers={"Authorization": "Bearer nope"}
    )
    assert wrong.status_code == 401


def test_requests_from_other_machines_or_names_are_refused(
    app: Starlette,
) -> None:
    with TestClient(
        app, base_url=f"http://{AUTHORITY}", client=("10.0.0.7", 50000)
    ) as remote:
        response = remote.delete(runtime_path(), headers=AUTH)
    assert response.status_code == 403

    # A page can reach a loopback server through a name it controls.
    with TestClient(
        app, base_url="http://evil.example:1234", client=("127.0.0.1", 50000)
    ) as rebinding:
        response = rebinding.delete(runtime_path(), headers=AUTH)
    assert response.status_code == 403
    assert response.json()["type"].endswith("/forbidden")


def test_the_host_api_sets_no_cookies_and_no_cors_headers(
    client: TestClient,
) -> None:
    origin = {"Origin": "http://localhost"}
    response = client.delete(runtime_path(), headers={**AUTH, **origin})
    assert "set-cookie" not in response.headers
    assert not [h for h in response.headers if h.startswith("access-control-")]

    ordinary = client.get("/health", headers=origin)
    assert "access-control-allow-credentials" in ordinary.headers


def test_an_operation_the_host_does_not_list_answers_501(
    app: Starlette,
) -> None:
    app.state.host_context.host = Host(
        host_of(app).state, FakeRuntime(), operations=["notebook.export"]
    )
    with TestClient(
        app, base_url=f"http://{AUTHORITY}", client=("127.0.0.1", 50000)
    ) as client:
        response = client.put(runtime_path(), json={}, headers=key("k"))
    assert response.status_code == 501
    assert response.json()["type"].endswith("/unsupported-operation")


def test_a_server_that_is_not_a_host_says_so(app: Starlette) -> None:
    app.state.host_context = None
    with TestClient(
        app, base_url=f"http://{AUTHORITY}", client=("127.0.0.1", 50000)
    ) as client:
        response = client.delete(runtime_path(), headers=AUTH)
    assert response.status_code == 404


# Runtimes


# Streams


async def read_until(
    app: Starlette,
    path: str,
    headers: dict[str, str],
    *,
    until: str,
    query: str = "",
) -> tuple[int, list[dict]]:  # type: ignore[type-arg]
    response, task, disconnect = request(
        app, "GET", path, headers=headers, query=query
    )
    done = asyncio.Event()

    async def watch() -> None:
        while True:
            if response.status not in (0, 200):
                done.set()
                return
            if any(r.get("event") == until for r in response.records):
                done.set()
                return
            await asyncio.sleep(0.01)

    watcher = asyncio.create_task(watch())
    try:
        await asyncio.wait_for(done.wait(), 10)
    finally:
        watcher.cancel()
        disconnect()
        await asyncio.gather(task, watcher, return_exceptions=True)
    return response.status, response.records


async def test_events_sends_the_snapshot_then_ready_with_a_cursor() -> None:
    from marimo._host.transitions import StartRuntime

    app, host, _ = make_app()
    host.command(StartRuntime(NOTEBOOK, RuntimeId("rt-1"), NOW, sandbox=False))

    status, records = await read_until(app, "/events", AUTH, until="ready")

    assert status == 200
    assert [r["event"] for r in records] == [
        "host",
        "project",
        "notebook",
        "runtime",
        "ready",
    ]
    assert records[0]["data"]["host"]["operations"] == OPERATIONS
    assert "id" not in records[0]
    assert records[-1] == {"event": "ready", "data": {}, "id": "1"}


async def test_events_resumes_from_a_cursor_and_can_be_filtered() -> None:
    from marimo._host.transitions import StartRuntime

    app, host, _ = make_app()
    host.command(StartRuntime(NOTEBOOK, RuntimeId("rt-1"), NOW, sandbox=False))
    host.observe(KernelReady(RuntimeId("rt-1"), 0, "0.25.0"))

    _, resumed = await read_until(
        app, "/events", {**AUTH, "Last-Event-ID": "1"}, until="ready"
    )
    assert [(r["event"], r.get("id")) for r in resumed] == [
        ("runtime", "2"),
        ("ready", "2"),
    ]

    _, runtimes_only = await read_until(
        app, "/events", AUTH, until="ready", query="types=runtime"
    )
    assert [r["event"] for r in runtimes_only] == ["runtime", "ready"]

    status, unauthorized = await read_until(app, "/events", {}, until="ready")
    assert (status, unauthorized) == (401, [])


async def test_a_notebook_stream_attaches_while_it_is_open() -> None:
    from marimo._host.transitions import StartRuntime

    app, host, _ = make_app()
    host.command(StartRuntime(NOTEBOOK, RuntimeId("rt-1"), NOW, sandbox=False))

    response, task, disconnect = request(
        app, "GET", f"/notebooks/{NOTEBOOK}/events", headers=AUTH
    )
    await wait_for(
        lambda: any(r.get("event") == "ready" for r in response.records)
    )
    names = [r["event"] for r in response.records]
    assert names == ["notebook", "runtime", "attachment", "ready"]
    attachment = response.records[2]["data"]["attachment"]
    assert attachment["notebook_id"] == NOTEBOOK
    assert attachment["kind"] == "client"
    assert list(host.state.notebooks[NOTEBOOK].attachments) == [
        attachment["id"]
    ]

    disconnect()
    await asyncio.gather(task, return_exceptions=True)
    assert host.state.notebooks[NOTEBOOK].attachments == {}

    unknown = await finished(
        app, "GET", "/notebooks/nope/events", headers=AUTH
    )
    assert unknown.status == 404
    assert json.loads(unknown.body)["type"].endswith("/not-found")
