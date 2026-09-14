# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from contextlib import aclosing
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from marimo._server.workspace import DirectoryWorkspace
from marimo._session.session import SessionImpl
from tests._server.discovery.test_api import _app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("running", [False, True])
async def test_stop_retains_state_and_leaves_notebook_and_server_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, running: bool
) -> None:
    path = tmp_path / "notebook.py"
    source = "import marimo\napp = marimo.App()\n@app.cell\ndef _():\n    x = 1\n    return (x,)\n"
    path.write_text(source)
    app, discovery = _app()
    manager = discovery.session_manager
    manager.workspace = DirectoryWorkspace(
        str(tmp_path), include_markdown=False
    )
    entered, release = asyncio.Event(), asyncio.Event()
    original = SessionImpl.create

    async def delayed(**kwargs: Any):
        entered.set()
        await release.wait()
        return await original(**kwargs)

    monkeypatch.setattr(SessionImpl, "create", delayed)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://localhost",
            headers={"Authorization": f"Bearer {discovery.token}"},
        ) as client:
            notebook = (await discovery.catalog()).projects[0].notebooks[0]
            started = await discovery.start_session(notebook.id)
            await asyncio.wait_for(entered.wait(), 5)
            url = f"/api/marimo/v1/sessions/{started.session_id}"
            async with aclosing(
                manager.watch_session(started.session_id)
            ) as updates:
                assert (await anext(updates)).status == "starting"
                if running:
                    release.set()
                    assert (
                        await asyncio.wait_for(anext(updates), 15)
                    ).status == "running"
                assert (
                    await client.delete(
                        url, headers={"Authorization": "Bearer wrong"}
                    )
                ).status_code == 401
                before = (await client.get(url)).json()
                stopped = await client.delete(url)
                assert stopped.status_code == 200
                assert stopped.json() == {**before, "status": "terminated"}
                assert (await anext(updates)).status == "terminated"
                assert (await client.delete(url)).json() == stopped.json()
                assert (await client.get(url)).json() == stopped.json()
            assert not manager.sessions
            assert path.read_text() == source
            catalog = (await client.get("/api/marimo/v1/catalog")).json()
            assert catalog["projects"][0]["notebooks"][0]["sessions"] == []
            assert (
                await client.delete("/api/marimo/v1/sessions/missing")
            ).status_code == 404
            again = await discovery.start_session(notebook.id)
            assert not again.reused
            assert again.session_id != started.session_id
    finally:
        release.set()
        await manager.shutdown()
        await discovery.close()


async def test_stopping_provisioning_survives_request_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, discovery = _app()
    manager = discovery.session_manager
    entered, cleaning, release = (
        asyncio.Event(),
        asyncio.Event(),
        asyncio.Event(),
    )

    async def provisioning(**_kwargs: Any):
        entered.set()
        try:
            await asyncio.Future()
        finally:
            cleaning.set()
            await release.wait()

    monkeypatch.setattr(SessionImpl, "create", provisioning)
    try:
        notebook = (await discovery.catalog()).projects[0].notebooks[0]
        started = await discovery.start_session(notebook.id)
        await asyncio.wait_for(entered.wait(), 5)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://localhost",
            headers={"Authorization": f"Bearer {discovery.token}"},
        ) as client:
            stopping = asyncio.create_task(
                client.delete(f"/api/marimo/v1/sessions/{started.session_id}")
            )
            await asyncio.wait_for(cleaning.wait(), 5)
            assert (
                discovery.read_session(started.session_id).status
                == "terminating"
            )
            conflict = await client.post(
                "/api/marimo/v1/sessions", json={"notebook_id": notebook.id}
            )
            assert conflict.status_code == 409
            stopping.cancel()
            with pytest.raises(asyncio.CancelledError):
                await stopping
            async with aclosing(
                manager.watch_session(started.session_id)
            ) as updates:
                assert (await anext(updates)).status == "terminating"
                release.set()
                assert (
                    await asyncio.wait_for(anext(updates), 5)
                ).status == "terminated"
    finally:
        release.set()
        await manager.shutdown()
        await discovery.close()
