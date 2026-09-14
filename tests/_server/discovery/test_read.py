# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import Mock
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from marimo._server import session_manager as session_manager_module
from marimo._session.types import KernelExitInfo, KernelState, Session
from marimo._types.ids import SessionId
from tests._server.discovery.test_api import _app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("exitcode", [None, 1], ids=["closed", "crashed"])
async def test_read_retains_terminal_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exitcode: int | None
) -> None:
    app, discovery = _app()
    manager = discovery.session_manager
    session = Mock(spec=Session)
    session.stable_id = str(uuid4())
    session.started_at = datetime.now(timezone.utc)
    session.initialization_id = str(tmp_path / "unindexed.py")
    session.app_file_manager = Mock(path=session.initialization_id)
    session.kernel_state.return_value = (
        KernelState.RUNNING if exitcode is None else KernelState.STOPPED
    )
    session.kernel_exit_info.return_value = KernelExitInfo(
        exitcode=exitcode, cause="exception", message="secret diagnostic"
    )

    def close_kernel() -> None:
        session.kernel_state.return_value = KernelState.STOPPED
        session.kernel_exit_info.return_value = None

    session.close.side_effect = close_kernel
    manager._repository.add_sync(SessionId("browser-id"), session)
    client = TestClient(
        app,
        client=("127.0.0.1", 50000),
        headers={"Authorization": f"Bearer {discovery.token}"},
    )
    url = f"/api/marimo/v1/sessions/{session.stable_id}"
    before = client.get(url)
    assert before.status_code == 200, before.text
    assert before.headers["cache-control"] == "no-store"
    assert before.json()["status"] == (
        "running" if exitcode is None else "failed"
    )
    monkeypatch.setattr(session_manager_module, "monotonic", lambda: 1000)
    assert manager.close_session(SessionId("browser-id"))
    assert not manager.sessions
    response = client.get(url)
    original = before.json()
    if exitcode is None:
        assert "error" not in original
    else:
        assert original["error"] == {
            "code": "KERNEL_EXITED",
            "message": f"Kernel exited with code {exitcode}",
        }
    expected = {
        **original,
        "status": "failed" if exitcode is not None else "terminated",
    }
    assert response.status_code == 200, response.text
    assert response.json() == expected
    assert "secret diagnostic" not in response.text
    assert all(
        not notebook["sessions"]
        for project in client.get("/api/marimo/v1/catalog").json()["projects"]
        for notebook in project["notebooks"]
    )
    monkeypatch.setattr(session_manager_module, "monotonic", lambda: 1299)
    assert client.get(url).json() == expected
    monkeypatch.setattr(session_manager_module, "monotonic", lambda: 1301)
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"message": "Session not found"}
