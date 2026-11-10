# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import contextlib
import tempfile
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from marimo._config.manager import (
    MarimoConfigManager,
    UserConfigStore,
    get_default_config_manager,
)
from marimo._server.config import StarletteServerStateInit
from marimo._server.lsp import NoopLspServer
from marimo._server.session_manager import SessionManager
from marimo._server.tokens import AuthToken, SkewProtectionToken
from marimo._server.workspace import (
    NotebookWorkspace,
    SingleFileWorkspace,
)
from marimo._session.model import SessionMode
from marimo._types.ids import CellId_t, SessionId
from marimo._utils.marimo_path import MarimoPath

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from httpx import Response
    from starlette.testclient import TestClient


def get_session_manager(client: TestClient) -> SessionManager:
    return client.app.state.session_manager  # type: ignore


def run_cells(
    client: TestClient,
    session_id: str,
    cells: dict[str, str],
    *,
    headers: dict[str, str],
) -> Response:
    """Put `cells` in the session's document and run them through the host.

    This is what the editor does: the document holds the code, and the run
    names the cells. Cells already in the document are replaced.
    """
    session = get_session_manager(client).get_session(SessionId(session_id))
    assert session is not None
    bridge = client.app.state.host_context.bridge  # type: ignore[union-attr]
    notebook = bridge.notebook_for_session(session)
    assert notebook is not None
    base = f"/api/marimo/v1/notebooks/{notebook.id}"

    def etag(cell_id: str) -> str | None:
        cell = notebook.document.cell(CellId_t(cell_id))
        return None if cell is None else cell.etag

    edited = client.post(
        f"{base}/edits",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={
            "changes": [
                {
                    "kind": "put_cell",
                    "base_etag": etag(cell_id),
                    "cell": {"id": cell_id, "code": code},
                }
                for cell_id, code in cells.items()
            ]
        },
    )
    assert edited.status_code == 200, edited.text
    return client.post(
        f"{base}/runtime/runs",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={"cells": [{"id": cell_id} for cell_id in cells]},
    )


def get_starlette_server_state_init(
    *,
    session_manager: SessionManager | None = None,
    base_url: str = "",
) -> StarletteServerStateInit:
    return StarletteServerStateInit(
        port=1234,
        host="localhost",
        base_url=base_url,
        asset_url=None,
        headless=False,
        quiet=False,
        session_manager=session_manager or get_mock_session_manager(),
        config_manager=MarimoConfigManager(UserConfigStore()),
        remote_url=None,
        mcp_server_enabled=False,
        skew_protection=False,
        enable_auth=True,
    )


def get_mock_session_manager(
    mode: SessionMode = SessionMode.EDIT,
) -> SessionManager:
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp_file:
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
        temp_file_path = temp_file.name

    lsp_server = NoopLspServer()

    sm = SessionManager(
        workspace=SingleFileWorkspace.from_path(MarimoPath(temp_file_path)),
        mode=mode,
        quiet=False,
        include_code=True,
        lsp_server=lsp_server,
        config_manager=get_default_config_manager(current_path=None),
        cli_args={},
        argv=None,
        auth_token=AuthToken("fake-token"),
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )
    sm._token_manager.skew_protection_token = SkewProtectionToken("skew-id-1")
    return sm


@contextlib.contextmanager
def workspace_scope(
    client: TestClient, workspace: NotebookWorkspace
) -> Iterator[None]:
    session_manager: SessionManager = cast(
        Any, client.app
    ).state.session_manager
    original_workspace = session_manager.workspace
    session_manager.workspace = workspace
    try:
        yield
    finally:
        session_manager.workspace = original_workspace


def with_workspace(
    workspace: NotebookWorkspace,
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorator to swap a workspace for the duration of the test."""

    def decorator(func: Callable[..., None]) -> Callable[..., None]:
        def wrapper(client: TestClient, *args: Any, **kwargs: Any) -> None:
            with workspace_scope(client, workspace):
                func(client, *args, **kwargs)

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
            temp_marimo_file: str | None,
        ) -> None:
            auth_token = get_session_manager(client).auth_token
            headers = token_header(auth_token)

            try:
                with client.websocket_connect(
                    f"/ws?session_id={session_id}", headers=headers
                ) as websocket:
                    from tests._server.api.endpoints.ws_helpers import (
                        receive_until,
                    )

                    data = receive_until("kernel-ready", websocket)
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
                    from tests._server.api.endpoints.ws_helpers import (
                        receive_until,
                    )

                    data = receive_until("kernel-ready", websocket)
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
    include_code: bool = True,
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorator to create a read session and close it after the test.

    Args:
        session_id: The session ID to use
        include_code: Whether code should be visible in run mode (default True)
    """

    def decorator(func: Callable[..., None]) -> Callable[..., None]:
        def wrapper(client: TestClient) -> None:
            session_manager = get_session_manager(client)
            headers = token_header(session_manager.auth_token)

            try:
                with client.websocket_connect(
                    f"/ws?session_id={session_id}", headers=headers
                ) as websocket:
                    from tests._server.api.endpoints.ws_helpers import (
                        receive_until,
                    )

                    data = receive_until("kernel-ready", websocket)
                    assert data
                    # Just change the mode here, otherwise our tests will run,
                    # in threads
                    original_mode = session_manager.mode
                    original_include_code = session_manager.include_code
                    session_manager.mode = SessionMode.RUN
                    session_manager.include_code = include_code
                    func(client)
                    session_manager.mode = original_mode
                    session_manager.include_code = original_include_code
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
    encoded = base64.b64encode(f"marimo:{token!s}".encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Marimo-Server-Token": skew_id,
    }
