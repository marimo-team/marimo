# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
import signal
from contextlib import aclosing
from dataclasses import replace
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from starlette.requests import ClientDisconnect, Request

from marimo._server.api.endpoints.discovery import watch_session
from marimo._session.session import SessionImpl
from tests._server.discovery.test_api import _app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.types import Message

    from marimo._session.types import Session


@pytest.mark.parametrize("ending", ["close", "crash"])
async def test_watch_progress_readiness_and_terminal_state(
    monkeypatch: pytest.MonkeyPatch, ending: str
) -> None:
    app, discovery = _app()
    manager = discovery.session_manager
    entered, release = asyncio.Event(), asyncio.Event()
    original_create = SessionImpl.create

    async def delayed_create(**kwargs: Any) -> Session:
        kwargs["on_progress"]("preparing-environment")
        entered.set()
        await release.wait()
        kwargs["on_progress"]("starting-kernel")
        return await original_create(**kwargs)

    monkeypatch.setattr(SessionImpl, "create", delayed_create)
    catalog = await discovery.catalog()
    notebook = catalog.projects[0].notebooks[0]
    selected = await discovery.start_session(notebook.id)
    url = f"/api/marimo/v1/sessions/{selected.session_id}"
    try:
        async with (
            aclosing(manager.watch_session(selected.session_id)) as events,
            aclosing(manager.watch_session(selected.session_id)) as slow,
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app),
                base_url="http://127.0.0.1",
                headers={"Authorization": f"Bearer {discovery.token}"},
            ) as client,
        ):
            initial = await anext(events)
            assert initial.status == "starting"
            assert initial.startup_phase is None
            assert await anext(slow) == initial
            await asyncio.wait_for(entered.wait(), 5)
            preparing = await asyncio.wait_for(anext(events), 5)
            assert preparing == replace(
                initial, startup_phase="preparing-environment"
            )
            assert (await client.get(url)).json()[
                "startup_phase"
            ] == "preparing-environment"
            release.set()
            ready = await asyncio.wait_for(anext(events), 15)
            if ready.status == "starting":
                assert ready == replace(
                    initial, startup_phase="starting-kernel"
                )
                ready = await asyncio.wait_for(anext(events), 15)
            assert ready == replace(initial, status="running")
            async with aclosing(
                manager.watch_session(selected.session_id)
            ) as late:
                assert await anext(late) == ready

            session_id, session = next(iter(manager.sessions.items()))
            if ending == "crash":
                pid = session.kernel_pid()
                assert pid is not None
                assert pid != os.getpid()
                os.kill(pid, signal.SIGTERM)
            else:
                session.close()
            terminal = await asyncio.wait_for(anext(events), 5)
            assert terminal.status == (
                "failed" if ending == "crash" else "terminated"
            )
            assert terminal.session_id == selected.session_id
            # Slow readers retain the outcome, without a backlog of progress.
            assert await asyncio.wait_for(anext(slow), 5) == terminal
            with pytest.raises(StopAsyncIteration):
                await anext(events)
            assert manager.close_session(session_id)
            assert (
                manager.get_session_snapshot(selected.session_id) == terminal
            )
            assert (
                not (await discovery.catalog())
                .projects[0]
                .notebooks[0]
                .sessions
            )
            details = (await client.get(url)).json()
            response = await asyncio.wait_for(client.get(url + "/watch"), 5)
            assert response.status_code == 200
            assert response.headers["content-type"].startswith(
                "text/event-stream"
            )
            event, data, blank = response.text.splitlines()
            assert event == "event: session.updated"
            assert json.loads(data.removeprefix("data: ")) == details
            assert blank == ""
    finally:
        release.set()
        await manager.shutdown()
        await discovery.close()


@pytest.mark.parametrize("asgi_spec", ["2.3", "2.4"])
async def test_watch_disconnect_releases_observer_without_canceling_startup(
    monkeypatch: pytest.MonkeyPatch, asgi_spec: str
) -> None:
    app, discovery = _app()
    manager = discovery.session_manager
    release, sent, closed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original_create = SessionImpl.create
    original_watch = discovery.watch_session

    async def delayed_create(**kwargs: Any) -> Session:
        await release.wait()
        return await original_create(**kwargs)

    async def observed(session_id: str) -> AsyncGenerator[str, None]:
        try:
            async with aclosing(original_watch(session_id)) as events:
                async for event in events:
                    yield event
        finally:
            closed.set()

    monkeypatch.setattr(SessionImpl, "create", delayed_create)
    monkeypatch.setattr(discovery, "watch_session", observed)
    catalog = await discovery.catalog()
    selected = await discovery.start_session(
        catalog.projects[0].notebooks[0].id
    )

    async def receive() -> Message:
        await sent.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        if message["type"] == "http.response.body":
            sent.set()
            if asgi_spec == "2.4":
                raise OSError("client disconnected")

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/api/marimo/v1/sessions/{selected.session_id}/watch",
            "path_params": {"session_id": selected.session_id},
            "headers": [],
            "query_string": b"",
            "app": app,
            "asgi": {"spec_version": asgi_spec},
        },
        receive=receive,
    )
    try:
        response = await watch_session(request=request)
        if asgi_spec == "2.4":
            with pytest.raises(ClientDisconnect):
                await asyncio.wait_for(
                    response(request.scope, receive, send), 5
                )
        else:
            await asyncio.wait_for(response(request.scope, receive, send), 5)
        assert closed.is_set()
        async with aclosing(
            manager.watch_session(selected.session_id)
        ) as events:
            assert (await anext(events)).status == "starting"
            release.set()
            assert (
                await asyncio.wait_for(anext(events), 15)
            ).status == "running"
    finally:
        release.set()
        await manager.shutdown()
        await discovery.close()


async def test_watch_rejects_unknown_session_before_streaming() -> None:
    app, discovery = _app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://127.0.0.1"
    ) as client:
        url = "/api/marimo/v1/sessions/missing/watch"
        assert (await client.get(url)).status_code == 401
        response = await client.get(
            url, headers={"Authorization": f"Bearer {discovery.token}"}
        )
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/json"
        assert response.json() == {"message": "Session not found"}
