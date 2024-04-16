# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import tempfile
from typing import Any, Callable, cast
from unittest.mock import MagicMock

from starlette.testclient import TestClient

from marimo._config.manager import UserConfigManager
from marimo._server.file_router import AppFileRouter
from marimo._server.model import SessionMode
from marimo._server.sessions import LspServer, SessionManager


def get_session_manager(client: TestClient) -> SessionManager:
    return client.app.state.session_manager  # type: ignore


def get_mock_session_manager() -> SessionManager:
    temp_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False)

    temp_file.write(
        """
import marimo

__generated_with = "0.0.1"
app = marimo.App(width="full")


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
""".encode()
    )

    temp_file.close()

    lsp_server = MagicMock(spec=LspServer)
    lsp_server.is_running.return_value = False

    sm = SessionManager(
        file_router=AppFileRouter.from_filename(temp_file.name),
        mode=SessionMode.EDIT,
        development_mode=False,
        quiet=False,
        include_code=True,
        lsp_server=lsp_server,
        user_config_manager=UserConfigManager(),
    )
    sm.server_token = "fake-token"
    return sm


def with_file_router(
    file_router: AppFileRouter,
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorator to create a session and close it after the test"""

    def decorator(func: Callable[..., None]) -> Callable[..., None]:
        def wrapper(client: TestClient, *args: Any, **kwargs: Any) -> None:
            session_manager: SessionManager = cast(
                Any, client.app
            ).state.session_manager
            original_file_router = session_manager.file_router
            session_manager.file_router = file_router

            func(client, *args, **kwargs)

            session_manager.file_router = original_file_router

        return wrapper

    return decorator


def with_session(
    session_id: str,
    auto_shutdown: bool = True,
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorator to create a session and close it after the test"""

    def decorator(func: Callable[..., None]) -> Callable[..., None]:
        def wrapper(client: TestClient) -> None:
            with client.websocket_connect(
                f"/ws?session_id={session_id}"
            ) as websocket:
                data = websocket.receive_text()
                assert data
                func(client)
            # shutdown after websocket exits, otherwise
            # test fails on Windows (loop closed twice)
            server_token: str = get_session_manager(client).server_token
            if auto_shutdown:
                client.post(
                    "/api/kernel/shutdown",
                    headers={"Marimo-Server-Token": server_token},
                )

        return wrapper

    return decorator


def with_read_session(
    session_id: str,
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorator to create a session and close it after the test"""

    def decorator(func: Callable[..., None]) -> Callable[..., None]:
        def wrapper(client: TestClient) -> None:
            session_manager = get_session_manager(client)

            with client.websocket_connect(
                f"/ws?session_id={session_id}"
            ) as websocket:
                data = websocket.receive_text()
                assert data
                # Just change the mode here, otherwise our tests will run,
                # in threads
                session_manager.mode = SessionMode.RUN
                func(client)
                session_manager.mode = SessionMode.EDIT
            # shutdown after websocket exits, otherwise
            # test fails on Windows (loop closed twice)
            server_token: str = session_manager.server_token
            client.post(
                "/api/kernel/shutdown",
                headers={"Marimo-Server-Token": server_token},
            )

        return wrapper

    return decorator
