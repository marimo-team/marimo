# Copyright 2026 Marimo. All rights reserved.
"""Host discovery records and server lifecycle."""

from __future__ import annotations

import asyncio
import os
import stat
import sys
from typing import TYPE_CHECKING

import msgspec
import pytest
import uvicorn

from marimo._core import backend as be, protocol
from marimo._server.host import HOST_API_PATH, record as record_module
from marimo._server.host.lifespan import host as host_lifespan
from marimo._server.host.record import host_url
from marimo._server.main import create_starlette_app
from marimo._utils.lifespans import Lifespans
from tests._core.conftest import (
    ScriptedBackend,
    add_notebook,
    project,
    record,
    runtime_id_of,
)
from tests._server.host.drive import finished
from tests._server.mocks import get_starlette_server_state_init

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("host", "loopback"),
    [
        ("0.0.0.0", "127.0.0.1"),
        ("127.0.0.1", "127.0.0.1"),
        ("127.1.2.3", "127.1.2.3"),
        ("localhost", "127.0.0.1"),
        ("LOCALHOST", "127.0.0.1"),
        ("::ffff:127.0.0.1", "127.0.0.1"),
        ("::1", "[::1]"),
        ("[::1]", "[::1]"),
        ("::", "[::1]"),
        ("[::]", "[::1]"),
    ],
)
def test_the_url_names_the_loopback_that_reaches_the_bind(
    host: str, loopback: str
) -> None:
    assert host_url(host, 2718, "/marimo") == (
        f"http://{loopback}:2718/marimo{HOST_API_PATH}"
    )


@pytest.mark.parametrize("host", ["192.168.1.5", "10.0.0.1", "fe80::1", "x"])
def test_an_unreachable_bind_has_no_url(host: str) -> None:
    assert host_url(host, 2718, "") is None


async def test_an_unreachable_bind_writes_no_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(record_module, "marimo_state_dir", lambda: tmp_path)
    app = create_starlette_app(
        base_url="", enable_auth=True, lifespan=Lifespans([host_lifespan])
    )
    state = get_starlette_server_state_init()
    state.apply(app.state)
    app.state.server = uvicorn.Server(
        uvicorn.Config(app, host="192.168.1.5", port=1234)
    )

    async with app.router.lifespan_context(app):
        assert list((tmp_path / "hosts-v1").glob("*.json")) == []
        assert app.state.host_context is not None


@pytest.mark.parametrize("external_port", [1234, 8443])
async def test_the_lifespan_serves_the_host_while_the_server_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, external_port: int
) -> None:
    monkeypatch.setattr(record_module, "marimo_state_dir", lambda: tmp_path)
    app = create_starlette_app(
        base_url="", enable_auth=True, lifespan=Lifespans([host_lifespan])
    )
    state = get_starlette_server_state_init()
    state.apply(app.state)
    app.state.port = external_port
    app.state.host = "proxy.example" if external_port != 1234 else "localhost"
    app.state.server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=1234)
    )

    async with app.router.lifespan_context(app):
        [path] = list((tmp_path / "hosts-v1").glob("*.json"))
        record = msgspec.json.decode(
            path.read_bytes(), type=protocol.HostRecord
        )
        assert record.url == f"http://127.0.0.1:1234{HOST_API_PATH}"
        assert record.process.pid == os.getpid()
        if sys.platform != "win32":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
            assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700

        probe = "/notebooks/x/runtime"
        refused = await finished(
            app, "DELETE", probe, headers={"Idempotency-Key": "k"}
        )
        assert refused.status == 401
        admitted = await finished(
            app,
            "DELETE",
            probe,
            headers={
                "Authorization": f"Bearer {record.token}",
                "Idempotency-Key": "k",
            },
        )
        assert admitted.status == 404

    assert list((tmp_path / "hosts-v1").glob("*.json")) == []


async def test_idle_host_expires_results_and_stops_maintenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(record_module, "marimo_state_dir", lambda: tmp_path)
    app = create_starlette_app(base_url="", enable_auth=True)
    get_starlette_server_state_init().apply(app.state)
    app.state.server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=1234)
    )
    async with host_lifespan(app):
        context = app.state.host_context
        host = context.bridge.host
        now = 0.0
        host.clock = context.clock = lambda: now
        host.update_project(project())
        notebook = await add_notebook(host, record(), ScriptedBackend())
        notebook.adopt(lambda _: None)
        notebook.observe(be.Running(runtime_id_of(notebook)))
        headers = {
            "Authorization": f"Bearer {context.token}",
            "Idempotency-Key": "run",
        }
        response = await finished(
            app,
            "POST",
            f"/notebooks/{notebook.id}/runtime/runs",
            headers=headers,
            body=b'{"code":"42"}',
        )
        assert response.status == 202
        run_id = protocol.RunId(response.json()["id"])
        eid = protocol.ExecutionId("execution")
        notebook.observe(
            be.Planned(run_id, (be.PlannedExecution(eid, None, "hash", "42"),))
        )
        notebook.observe(be.Concluded(eid, protocol.ValueOutcome(None)))
        notebook.observe(be.Status(eid, "completed"))
        notebook.observe(be.Done(run_id, "succeeded"))
        removed = asyncio.Event()
        host.subscribe(
            lambda event: (
                removed.set() if event.name == "run.removed" else None
            ),
            notebook_id=notebook.id,
        )
        [maintenance] = [
            task
            for task in asyncio.all_tasks()
            if task.get_name() == "host.retention"
        ]
        now = 300
        await asyncio.wait_for(removed.wait(), timeout=5)
        assert context.replies == {}
    assert maintenance.done()
    assert app.state.host_context is None
