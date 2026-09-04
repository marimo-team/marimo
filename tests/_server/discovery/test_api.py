# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from dirty_equals import IsStr, IsUUID
from inline_snapshot import snapshot
from starlette.testclient import TestClient

from marimo._runtime.commands import ExecuteScratchpadCommand
from marimo._server import scratchpad as scratchpad_mod
from marimo._server.discovery.manager import DiscoveryManager
from marimo._server.main import create_starlette_app
from marimo._server.workspace import DirectoryWorkspace, SingleFileWorkspace
from marimo._session.types import KernelState
from marimo._utils.marimo_path import MarimoPath
from tests._server.mocks import (
    get_mock_session_manager,
    get_session_manager,
    get_starlette_server_state_init,
    with_session,
)

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.applications import Starlette


def _app() -> tuple[Starlette, DiscoveryManager]:
    session_manager = get_mock_session_manager()
    manager = DiscoveryManager(
        session_manager=session_manager,
        browser_url="http://127.0.0.1:2718",
        kind="marimo",
        name="marimo CLI",
    )
    app = create_starlette_app(
        base_url="", enable_auth=True, skew_protection=True
    )
    replace(
        get_starlette_server_state_init(session_manager=session_manager),
        discovery_manager=manager,
        skew_protection=True,
    ).apply(app.state)
    return app, manager


def test_catalog_requires_discovery_bearer_and_loopback() -> None:
    app, manager = _app()
    local = TestClient(app, client=("127.0.0.1", 50000))

    response = local.get("/api/marimo/v1/catalog")
    assert response.status_code == 401
    assert response.json() == {"message": "Invalid discovery token"}
    assert response.headers["cache-control"] == "no-store"

    response = local.get(
        "/api/marimo/v1/catalog",
        headers={
            "Authorization": f"Bearer {manager.token}",
            "Origin": "http://localhost",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == snapshot(
        {
            "instance_id": IsUUID(),
            "operations": [
                "catalog.watch",
                "notebook.open",
                "session.execute",
            ],
            "projects": [
                {
                    "id": IsUUID(),
                    "name": IsStr(),
                    "root": IsStr(),
                    "truncated": False,
                    "notebooks": [
                        {
                            "id": IsUUID(),
                            "title": IsStr(),
                            "openable": True,
                            "path": IsStr(),
                            "updated_at": IsStr(),
                            "sessions": [],
                        }
                    ],
                }
            ],
        }
    )
    assert response.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in response.headers

    remote = TestClient(app, client=("192.168.1.20", 50000))
    response = remote.get(
        "/api/marimo/v1/catalog",
        headers={"Authorization": f"Bearer {manager.token}"},
    )
    assert response.status_code == 403
    assert response.json() == {"message": "Loopback connection required"}


@pytest.mark.parametrize("directory_workspace", [False, True])
@pytest.mark.parametrize(
    ("folder", "filename"),
    [
        ("plain", "notebook.py"),
        ("plain", "café.py"),
        ("données", "notebook.py"),
    ],
)
def test_open_returns_absolute_one_time_uri(
    tmp_path: Path, directory_workspace: bool, folder: str, filename: str
) -> None:
    app, manager = _app()
    directory = tmp_path / folder
    directory.mkdir()
    path = directory / filename
    path.write_text("import marimo\napp = marimo.App()\n")
    manager.session_manager.workspace = (
        DirectoryWorkspace(str(directory), include_markdown=False)
        if directory_workspace
        else SingleFileWorkspace.from_path(MarimoPath(str(path)))
    )
    client = TestClient(app, client=("::1", 50000))
    headers = {"Authorization": f"Bearer {manager.token}"}
    catalog = client.get("/api/marimo/v1/catalog", headers=headers).json()
    notebook_id = catalog["projects"][0]["notebooks"][0]["id"]

    response = client.post(
        f"/api/marimo/v1/notebooks/{notebook_id}/open", headers=headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["uri"].startswith("http://127.0.0.1:2718/")
    assert response.headers["cache-control"] == "no-store"

    opened = urlsplit(response.json()["uri"])
    target = f"{opened.path}?{opened.query}"
    browser = TestClient(
        app,
        client=("::1", 50001),
        follow_redirects=False,
    )
    bootstrap = parse_qs(opened.query)["access_token"][0]
    expected_key = filename if directory_workspace else str(path)
    assert parse_qs(opened.query)["file"] == [expected_key]

    misuse = browser.get(f"/api/status?access_token={bootstrap}")
    assert misuse.status_code == 401
    wrong_query = urlencode({"file": "other.py", "access_token": bootstrap})
    wrong_target = f"{opened.path}?{wrong_query}"
    misbound = browser.get(wrong_target)
    assert misbound.status_code == 303
    assert "/auth/login" in misbound.headers["location"]

    exchange = browser.get(target)
    assert exchange.status_code == 303
    assert "access_token" not in exchange.headers["location"]
    assert "file=" in exchange.headers["location"]
    assert "set-cookie" in exchange.headers
    assert browser.get(exchange.headers["location"]).status_code == 200

    replay = TestClient(
        app,
        client=("127.0.0.1", 50002),
        follow_redirects=False,
    ).get(target)
    assert replay.status_code == 303
    assert "/auth/login" in replay.headers["location"]


def test_discovery_is_404_when_not_published() -> None:
    app = create_starlette_app(base_url="", enable_auth=True)
    get_starlette_server_state_init().apply(app.state)
    client = TestClient(app, client=("127.0.0.1", 50000))

    response = client.get("/api/marimo/v1/catalog")

    assert response.status_code == 404
    assert response.json() == {"message": "Not found"}


@with_session("discovery-session")
def test_execute_reuses_scratchpad_sse(client: TestClient) -> None:
    session_manager = get_session_manager(client)
    manager = DiscoveryManager(
        session_manager=session_manager,
        browser_url="http://127.0.0.1:2718",
        kind="marimo",
        name="marimo CLI",
    )
    client.app.state.discovery_manager = manager
    local = TestClient(client.app, client=("127.0.0.1", 50000))
    session = session_manager.sessions[next(iter(session_manager.sessions))]
    headers = {"Authorization": f"Bearer {manager.token}"}
    snapshot = local.get("/api/marimo/v1/catalog", headers=headers).json()
    discovered_session = snapshot["projects"][0]["notebooks"][0]["sessions"][0]
    assert discovered_session["session_id"] == "discovery-session"
    assert discovered_session["status"] == "running"
    assert discovered_session["mode"] == "edit"
    captured: list[object] = []

    def capture(command: object, from_consumer_id: object) -> None:
        del from_consumer_id
        captured.append(command)

    async def empty_stream(self: object):
        del self
        if False:
            yield ""

    with (
        patch.object(session, "put_control_request", side_effect=capture),
        patch.object(
            scratchpad_mod.ScratchCellListener, "stream", empty_stream
        ),
    ):
        response = local.post(
            "/api/marimo/v1/sessions/discovery-session/execute",
            headers=headers,
            json={"code": "print('hello from discovery')"},
        )

    assert response.status_code == 200, response.text
    assert "event: done" in response.text
    assert '"success": true' in response.text
    commands = [
        command
        for command in captured
        if isinstance(command, ExecuteScratchpadCommand)
    ]
    assert len(commands) == 1
    http_request = commands[0].request
    assert http_request is not None
    assert "authorization" not in http_request.headers
    assert http_request.cookies == {}
    assert http_request.user == {}
    assert http_request.meta["screenshot_auth_token"] != manager.token

    invalid = local.post(
        "/api/marimo/v1/sessions/discovery-session/execute",
        headers=headers,
        json={},
    )
    assert invalid.status_code == 400
    assert set(invalid.json()) == {"message"}

    with patch.object(
        session, "kernel_state", return_value=KernelState.STOPPED
    ):
        stopped = local.post(
            "/api/marimo/v1/sessions/discovery-session/execute",
            headers=headers,
            json={"code": "1 + 1"},
        )
    assert stopped.status_code == 409
    assert stopped.json() == {"message": "Session is not running"}


def test_execute_errors_use_protocol_shape() -> None:
    app, manager = _app()
    client = TestClient(app, client=("127.0.0.1", 50000))
    headers = {"Authorization": f"Bearer {manager.token}"}

    response = client.post(
        "/api/marimo/v1/sessions/missing/execute",
        headers=headers,
        json={"code": "1 + 1"},
    )

    assert response.status_code == 404
    assert response.json() == {"message": "Session not found"}
