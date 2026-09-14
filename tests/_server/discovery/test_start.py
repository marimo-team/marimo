# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, Mock

import httpx
import pytest
from starlette.requests import HTTPConnection

from marimo._server.api.endpoints.ws.ws_connection_validator import (
    ConnectionParams,
)
from marimo._server.api.endpoints.ws.ws_session_connector import (
    ConnectionType,
    SessionConnector,
)
from marimo._server.workspace import DirectoryWorkspace
from marimo._session.consumer import SessionConsumer
from marimo._session.model import ConnectionState
from marimo._session.session import SessionImpl
from marimo._session.types import Session
from marimo._types.ids import SessionId
from tests._server.discovery.test_api import _app

if TYPE_CHECKING:
    from pathlib import Path


async def test_start_survives_request_and_browser_joins_without_running_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "executed"
    (tmp_path / "notebook.py").write_text(
        "import marimo\napp = marimo.App()\n@app.cell\ndef _():\n"
        f"    from pathlib import Path\n    Path({str(marker)!r}).touch()\n    return\n"
    )
    app, discovery = _app()
    manager = discovery.session_manager
    manager.workspace = DirectoryWorkspace(
        str(tmp_path), include_markdown=False
    )
    entered, release = asyncio.Event(), asyncio.Event()
    original_create = SessionImpl.create
    launches = 0

    async def delayed_create(**kwargs: Any):
        nonlocal launches
        launches += 1
        entered.set()
        await release.wait()
        return await original_create(**kwargs)

    monkeypatch.setattr(SessionImpl, "create", delayed_create)
    transport = httpx.ASGITransport(app)
    headers = {"Authorization": f"Bearer {discovery.token}"}
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost", headers=headers
        ) as client:
            catalog = (await client.get("/api/marimo/v1/catalog")).json()
            notebook = catalog["projects"][0]["notebooks"][0]
            results = await asyncio.gather(
                *(
                    client.post(
                        "/api/marimo/v1/sessions",
                        json={"notebook_id": notebook["id"]},
                    )
                    for _ in range(2)
                )
            )
            assert sorted(response.status_code for response in results) == [
                200,
                201,
            ]
            created = next(
                response.json()
                for response in results
                if response.status_code == 201
            )
            reused = next(
                response.json()
                for response in results
                if response.status_code == 200
            )
            assert reused == {**created, "reused": True}
            assert created.pop("reused") is False
            assert created["status"] == "starting"
            assert created["notebook_id"] == notebook["id"]
            url = f"/api/marimo/v1/sessions/{created['session_id']}"
            await asyncio.wait_for(entered.wait(), 5)
            pending_catalog = (
                await client.get("/api/marimo/v1/catalog")
            ).json()
            pending = pending_catalog["projects"][0]["notebooks"][0][
                "sessions"
            ][0]
            assert (pending["session_id"], pending["status"]) == (
                created["session_id"],
                "starting",
            )
            premature = await client.post(
                url + "/execute", json={"code": "print('too early')"}
            )
            assert premature.status_code == 409
            assert premature.json() == {"message": "Session is not running"}

        # A browser arrives after the initiating HTTP client has gone away.
        connector = SessionConnector(
            manager=manager,
            handler=MagicMock(),
            params=ConnectionParams(
                session_id=SessionId("browser"),
                file_key="notebook.py",
                kiosk=False,
                auto_instantiate=True,
                rtc_enabled=False,
            ),
            connection=HTTPConnection({"type": "http", "query_string": b""}),
        )
        browser = asyncio.create_task(connector.connect())
        release.set()
        session, kind = await asyncio.wait_for(browser, 15)
        assert kind is ConnectionType.RESUME
        assert session.stable_id == created["session_id"]
        assert launches == 1

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://localhost",
            headers=headers,
        ) as client:
            ready = (await client.get(url)).json()
            assert ready == {**created, "status": "running"}
            executed = await asyncio.wait_for(
                client.post(
                    url + "/execute",
                    json={
                        "code": "import builtins\nbuiltins._discovery_start_test = 42"
                    },
                ),
                15,
            )
            assert executed.status_code == 200, executed.text
            assert '"success": true' in executed.text
            assert not marker.exists()
            again = await client.post(
                "/api/marimo/v1/sessions", json={"notebook_id": notebook["id"]}
            )
            assert again.status_code == 200
            assert again.json() == {**ready, "reused": True}
            executed = await asyncio.wait_for(
                client.post(
                    url + "/execute",
                    json={
                        "code": "print(__import__('builtins')._discovery_start_test)"
                    },
                ),
                15,
            )
            assert "42" in executed.text
            assert '"success": true' in executed.text
    finally:
        release.set()
        await manager.shutdown()
        await discovery.close()


async def test_failed_start_is_retained_and_can_be_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, discovery = _app()
    manager = discovery.session_manager
    entered, release = asyncio.Event(), asyncio.Event()
    startup: asyncio.Task[object] | None = None

    async def fail(**_kwargs: object):
        nonlocal startup
        startup = asyncio.current_task()
        entered.set()
        await release.wait()
        raise RuntimeError("private provisioning diagnostic")

    monkeypatch.setattr(SessionImpl, "create", fail)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://localhost",
            headers={"Authorization": f"Bearer {discovery.token}"},
        ) as client:
            catalog = (await client.get("/api/marimo/v1/catalog")).json()
            notebook = catalog["projects"][0]["notebooks"][0]
            response = await client.post(
                "/api/marimo/v1/sessions", json={"notebook_id": notebook["id"]}
            )
            assert response.status_code == 201
            created = response.json()
            await asyncio.wait_for(entered.wait(), 5)
            assert startup is not None
            release.set()
            with pytest.raises(
                RuntimeError, match="private provisioning diagnostic"
            ):
                await asyncio.wait_for(startup, 5)
            failed = await client.get(
                f"/api/marimo/v1/sessions/{created['session_id']}"
            )
            assert failed.status_code == 200
            expected = {
                key: value for key, value in created.items() if key != "reused"
            }
            assert failed.json() == {
                **expected,
                "status": "failed",
                "error": {
                    "code": "KERNEL_START_FAILED",
                    "message": "Kernel failed to start",
                },
            }
            restarted = await client.post(
                "/api/marimo/v1/sessions", json={"notebook_id": notebook["id"]}
            )
            assert restarted.status_code == 201
            assert not restarted.json()["reused"]
            assert restarted.json()["session_id"] != created["session_id"]
            assert (
                await client.get(
                    f"/api/marimo/v1/sessions/{created['session_id']}"
                )
            ).json() == failed.json()
    finally:
        release.set()
        await manager.shutdown()
        await discovery.close()


async def test_discovery_keeps_startup_after_browser_disconnects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, discovery = _app()
    manager = discovery.session_manager
    file_key = manager.workspace.get_unique_file_key()
    assert file_key is not None
    consumer = Mock(spec=SessionConsumer)
    consumer.connection_state.return_value = ConnectionState.OPEN
    entered, release = asyncio.Event(), asyncio.Event()
    original_create = SessionImpl.create
    startup: asyncio.Task[Session] | None = None

    async def delayed_create(**kwargs: Any) -> Session:
        nonlocal startup
        startup = asyncio.current_task()
        entered.set()
        await release.wait()
        return await original_create(**kwargs)

    monkeypatch.setattr(SessionImpl, "create", delayed_create)
    browser = asyncio.create_task(
        manager.create_session(
            SessionId("browser"), consumer, {}, file_key, False
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        catalog = await discovery.catalog()
        selected = await discovery.start_session(
            catalog.projects[0].notebooks[0].id
        )
        assert selected.reused
        assert selected.status == "starting"

        consumer.connection_state.return_value = ConnectionState.CLOSED
        browser.cancel()
        with pytest.raises(asyncio.CancelledError):
            await browser
        assert startup is not None
        release.set()
        session = await asyncio.wait_for(startup, 15)
        assert session.stable_id == selected.session_id
        assert session.connection_state() is ConnectionState.ORPHANED
        assert discovery.read_session(selected.session_id).status == "running"
    finally:
        release.set()
        await manager.shutdown()
        await discovery.close()
