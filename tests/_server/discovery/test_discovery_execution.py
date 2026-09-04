# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs

import httpx
import pytest
from starlette.requests import ClientDisconnect, Request

from marimo._code_mode.screenshot import _ScreenshotSession
from marimo._messaging.notebook.document import NotebookDocument
from marimo._server.api.endpoints.discovery import execute
from marimo._server.discovery.manager import DiscoveryManager
from marimo._server.main import create_starlette_app
from marimo._server.tokens import AuthToken
from marimo._server.workspace import DirectoryWorkspace
from marimo._session.state.session_view import SessionView
from marimo._session.types import KernelState, Session
from marimo._types.ids import SessionId
from tests._server.mocks import (
    get_mock_session_manager,
    get_starlette_server_state_init,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from starlette.applications import Starlette
    from starlette.types import Message


def execution_app(
    tmp_path: Path, *, auth: bool = True, base_url: str = ""
) -> tuple[Starlette, DiscoveryManager, Mock]:
    (tmp_path / "café & tea.py").write_text(
        "import marimo\napp = marimo.App()\n"
    )
    sm = get_mock_session_manager()
    sm.workspace = DirectoryWorkspace(str(tmp_path), include_markdown=False)
    if not auth:
        sm._token_manager.auth_token = AuthToken("")
    session = Mock(spec=Session)
    session.initialization_id = "café & tea.py"
    session.app_file_manager = Mock(
        path=str(tmp_path / session.initialization_id)
    )
    session.kernel_state.return_value = KernelState.RUNNING
    session.scratchpad_lock = asyncio.Lock()
    session.scoped.return_value = nullcontext()
    session.document = NotebookDocument()
    session.session_view = SessionView()
    sm._repository.add_sync(SessionId("session"), session)
    manager = DiscoveryManager(
        session_manager=sm,
        browser_url=f"http://127.0.0.1:2718{base_url}",
        kind="marimo",
        name="marimo",
    )
    app = create_starlette_app(base_url=base_url, enable_auth=auth)
    replace(
        get_starlette_server_state_init(session_manager=sm, base_url=base_url),
        discovery_manager=manager,
        enable_auth=auth,
    ).apply(app.state)
    return app, manager, session


@pytest.mark.parametrize("auth", [True, False])
@pytest.mark.parametrize("base_url", ["", "/notebooks"])
@pytest.mark.parametrize("queued", [True, False])
async def test_execution_screenshot_reaches_notebook_after_delays(
    tmp_path: Path, auth: bool, base_url: str, queued: bool
) -> None:
    app, manager, session = execution_app(
        tmp_path, auth=auth, base_url=base_url
    )
    instantiated = asyncio.Event()
    session.instantiate.side_effect = lambda *_args, **_kwargs: (
        instantiated.set()
    )
    now = datetime.now(timezone.utc)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://127.0.0.1:2718"
    ) as client:

        async def kernel_stream(listener: object) -> AsyncGenerator[str, None]:
            del listener
            clock.now.return_value += timedelta(minutes=2)
            command = session.put_control_request.call_args.args[0]
            meta = command.request.meta
            screenshot = _ScreenshotSession(
                meta["screenshot_server_url"], meta["screenshot_auth_token"]
            )
            page = AsyncMock()
            screenshot._page = page
            await screenshot._navigate(initial=True)
            url = page.goto.call_args.args[0]
            response = await client.get(url, follow_redirects=True)
            assert response.status_code == 200
            assert response.url.path == f"{base_url}/"
            assert parse_qs(response.url.query.decode()) == {
                "file": ["café & tea.py"],
                "kiosk": ["true"],
            }
            yield 'event: stdout\ndata: {"data":"screenshot complete"}\n\n'

        with (
            patch(
                "marimo._server.discovery.manager.datetime", wraps=datetime
            ) as clock,
            patch(
                "marimo._server.scratchpad.ScratchCellListener.stream",
                kernel_stream,
            ),
        ):
            clock.now.return_value = now
            if queued:
                await session.scratchpad_lock.acquire()
            task = asyncio.create_task(
                client.post(
                    f"{base_url}/api/marimo/v1/sessions/session/execute",
                    headers={"Authorization": f"Bearer {manager.token}"},
                    json={"code": "take a screenshot"},
                )
            )
            try:
                await asyncio.wait_for(instantiated.wait(), 2)
                if queued:
                    clock.now.return_value += timedelta(minutes=2)
                    session.scratchpad_lock.release()
                response = await asyncio.wait_for(task, 5)
                assert response.status_code == 200
                assert "event: done" in response.text
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize(
    "ending",
    [
        "complete",
        "cancel_queued",
        "cancel_running",
        "send_error",
        "start_error",
        "execution_error",
    ],
)
@pytest.mark.parametrize("asgi_spec", ["2.3", "2.4"])
async def test_execution_revokes_unused_browser_token(
    tmp_path: Path, ending: str, asgi_spec: str
) -> None:
    app, manager, session = execution_app(tmp_path)
    started = asyncio.Event()
    running = asyncio.Event()

    def instantiate(*_args: object, **_kwargs: object) -> None:
        started.set()
        if ending == "start_error":
            raise RuntimeError("kernel is gone")

    session.instantiate.side_effect = instantiate

    async def kernel_stream(listener: object) -> AsyncGenerator[str, None]:
        del listener
        if ending == "execution_error":
            raise RuntimeError("kernel execution failed")
        yield 'event: stdout\ndata: {"data":"hello"}\n\n'
        if ending == "cancel_running":
            running.set()
            await asyncio.Future()

    async def receive() -> Message:
        if not started.is_set():
            return {"type": "http.request", "body": b'{"code":"pass"}'}
        return await asyncio.Future()

    messages: list[Message] = []

    async def send(message: Message) -> None:
        messages.append(message)
        if ending == "send_error" and message["type"] == "http.response.body":
            raise OSError("client disconnected")

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/marimo/v1/sessions/session/execute",
            "path_params": {"session_id": "session"},
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("127.0.0.1", 2718),
            "app": app,
            "asgi": {"spec_version": asgi_spec},
        },
        receive=receive,
    )
    with patch(
        "marimo._server.scratchpad.ScratchCellListener.stream", kernel_stream
    ):
        if ending == "cancel_queued":
            await session.scratchpad_lock.acquire()
        response = await execute(request)
        task = asyncio.create_task(response(request.scope, receive, send))
        try:
            await asyncio.wait_for(started.wait(), 2)
            if ending in {"cancel_queued", "cancel_running"}:
                if ending == "cancel_running":
                    await asyncio.wait_for(running.wait(), 2)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            elif ending == "send_error":
                with pytest.raises(
                    ClientDisconnect if asgi_spec == "2.4" else OSError
                ):
                    await task
            elif ending == "execution_error":
                with pytest.raises(
                    RuntimeError, match="kernel execution failed"
                ):
                    await task
            else:
                await asyncio.wait_for(task, 2)
                assert messages[0]["status"] == (
                    500 if ending == "start_error" else 200
                )
            token = session.instantiate.call_args.kwargs["http_request"].meta[
                "screenshot_auth_token"
            ]
            assert token
            assert manager.consume_browser_token(token, None) is None
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if ending == "cancel_queued":
                session.scratchpad_lock.release()


def test_open_token_expiry_is_independent_of_execution_scope(
    tmp_path: Path,
) -> None:
    _, manager, session = execution_app(tmp_path)
    now = datetime.now(timezone.utc)
    with patch(
        "marimo._server.discovery.manager.datetime", wraps=datetime
    ) as clock:
        clock.now.return_value = now
        open_token = manager.issue_browser_token(session.initialization_id)
        with manager.execution_credentials(session) as (_, execution_token):
            clock.now.return_value += timedelta(minutes=2)
            assert manager.consume_browser_token(open_token, None) is None
            assert (
                manager.consume_browser_token(execution_token, None)
                == session.initialization_id
            )
            assert manager.consume_browser_token(execution_token, None) is None
