# Copyright 2024 Marimo. All rights reserved.
import functools
import tempfile
from typing import Callable

from starlette.testclient import TestClient

from marimo._server.model import SessionMode
from marimo._server.sessions import SessionManager


@functools.lru_cache()
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
    mo.md("# Hello Marimo!")
    return mo,


if __name__ == "__main__":
    app.run()
""".encode()
    )

    return SessionManager(
        filename=temp_file.name,
        mode=SessionMode.EDIT,
        port=1001,
        development_mode=False,
        quiet=False,
        include_code=True,
    )


def with_session(
    session_id: str,
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorator to create a session and close it after the test"""

    def decorator(func: Callable[..., None]):
        def wrapper(client: TestClient):
            with client.websocket_connect(
                f"/ws?session_id={session_id}"
            ) as websocket:
                data = websocket.receive_text()
                assert data
                func(client)
                client.post("/api/kernel/shutdown")

        return wrapper

    return decorator
