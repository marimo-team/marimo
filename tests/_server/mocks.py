# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
import tempfile
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

from marimo._config.manager import get_default_config_manager
from marimo._server.file_router import AppFileRouter
from marimo._server.model import SessionMode
from marimo._server.sessions import NoopLspServer, SessionManager
from marimo._server.tokens import AuthToken, SkewProtectionToken
from marimo._utils.marimo_path import MarimoPath

if TYPE_CHECKING:
    from starlette.testclient import TestClient


def get_session_manager(client: TestClient) -> SessionManager:
    return client.app.state.session_manager  # type: ignore


def get_mock_session_manager() -> SessionManager:
    temp_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False)

    temp_file.write(
        b"""
import marimo

__generated_with = "0.0.1"
app = marimo.App(width="full")


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
"""
    )

    temp_file.close()

    lsp_server = NoopLspServer()

    sm = SessionManager(
        file_router=AppFileRouter.from_filename(MarimoPath(temp_file.name)),
        mode=SessionMode.EDIT,
        development_mode=False,
        quiet=False,
        include_code=True,
        lsp_server=lsp_server,
        config_manager=get_default_config_manager(current_path=None),
        cli_args={},
        auth_token=AuthToken("fake-token"),
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )
    sm.skew_protection_token = SkewProtectionToken("skew-id-1")
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
        def wrapper(
            client: TestClient,
            temp_marimo_file: Optional[str],
        ) -> None:
            auth_token = get_session_manager(client).auth_token
            headers = token_header(auth_token)

            try:
                with client.websocket_connect(
                    f"/ws?session_id={session_id}", headers=headers
                ) as websocket:
                    data = websocket.receive_text()
                    assert data
                    if "temp_marimo_file" in func.__code__.co_varnames:
                        func(
                            client,
                            temp_marimo_file=temp_marimo_file,
                        )
                    else:
                        func(client)
            finally:
                # Always shutdown, even if there's an error
                if auto_shutdown:
                    client.post(
                        "/api/kernel/shutdown",
                        headers=headers,
                    )

        return wrapper

    return decorator


def with_websocket_session(
    session_id: str,
    auto_shutdown: bool = True,
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorator to create a session and close it after the test"""

    def decorator(func: Callable[..., None]) -> Callable[..., None]:
        def wrapper(client: TestClient) -> None:
            auth_token = get_session_manager(client).auth_token
            headers = token_header(auth_token)

            try:
                with client.websocket_connect(
                    f"/ws?session_id={session_id}", headers=headers
                ) as websocket:
                    data = websocket.receive_text()
                    assert data

                    func(client, websocket)
            finally:
                # Always shutdown, even if there's an error
                if auto_shutdown:
                    client.post(
                        "/api/kernel/shutdown",
                        headers=headers,
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
            headers = token_header(session_manager.auth_token)

            try:
                with client.websocket_connect(
                    f"/ws?session_id={session_id}", headers=headers
                ) as websocket:
                    data = websocket.receive_text()
                    assert data
                    # Just change the mode here, otherwise our tests will run,
                    # in threads
                    session_manager.mode = SessionMode.RUN
                    func(client)
                    session_manager.mode = SessionMode.EDIT
            finally:
                # Always shutdown, even if there's an error
                client.post(
                    "/api/kernel/shutdown",
                    headers=headers,
                )

        return wrapper

    return decorator


def token_header(
    token: str | AuthToken = "fake-token", skew_id: str = "skew-id-1"
) -> dict[str, str]:
    encoded = base64.b64encode(f"marimo:{str(token)}".encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Marimo-Server-Token": skew_id,
    }
