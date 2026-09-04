# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from dirty_equals import IsStr, IsUUID
from inline_snapshot import snapshot
from starlette.testclient import TestClient

from marimo._server.discovery.manager import DiscoveryManager
from marimo._server.main import create_starlette_app
from tests._server.mocks import (
    get_mock_session_manager,
    get_starlette_server_state_init,
)

if TYPE_CHECKING:
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


def test_discovery_is_404_when_not_published() -> None:
    app = create_starlette_app(base_url="", enable_auth=True)
    get_starlette_server_state_init().apply(app.state)
    client = TestClient(app, client=("127.0.0.1", 50000))

    response = client.get("/api/marimo/v1/catalog")

    assert response.status_code == 404
    assert response.json() == {"message": "Not found"}
