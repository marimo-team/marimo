# Copyright 2024 Marimo. All rights reserved.
import tempfile
from typing import Callable
from unittest.mock import MagicMock

from starlette.testclient import TestClient

from marimo._server.model import SessionMode
from marimo._server.sessions import LspServer, SessionManager


def get_mock_session_manager() -> SessionManager:
    temp_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False)

    temp_file.write(
        """
import marimo

__generated_with = "0.0.1"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
""".encode()
    )

    temp_file.close()

    sm = SessionManager(
        filename=temp_file.name,
        mode=SessionMode.EDIT,
        development_mode=False,
        quiet=False,
        include_code=True,
        lsp_server=MagicMock(spec=LspServer),
    )
    sm.server_token = "fake-token"
    return sm


def with_session(
    session_id: str,
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
            server_token: str = client.app.state.session_manager.server_token  # type: ignore  # noqa: E501
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
            with client.websocket_connect(
                f"/ws?session_id={session_id}"
            ) as websocket:
                data = websocket.receive_text()
                assert data
                # Just change the mode here, otherwise our tests will run,
                # in threads
                client.app.state.session_manager.mode = SessionMode.RUN  # type: ignore  # noqa: E501
                func(client)
                client.app.state.session_manager.mode = SessionMode.EDIT  # type: ignore  # noqa: E501
            # shutdown after websocket exits, otherwise
            # test fails on Windows (loop closed twice)
            server_token: str = client.app.state.session_manager.server_token  # type: ignore  # noqa: E501
            client.post(
                "/api/kernel/shutdown",
                headers={"Marimo-Server-Token": server_token},
            )

        return wrapper

    return decorator
