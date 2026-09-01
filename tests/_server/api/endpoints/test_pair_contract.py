# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from marimo import __version__
from marimo._runtime.commands import ExecuteScratchpadCommand
from marimo._server.scratchpad import ScratchCellListener
from marimo._types.ids import SessionId
from tests._server.mocks import (
    get_session_manager,
    token_header,
    with_session,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.testclient import TestClient


PAIR_SESSION_ID = SessionId("pair-session")
PAIR_HEADERS = {
    "Marimo-Session-Id": PAIR_SESSION_ID,
    **token_header("fake-token"),
}
FIXTURE_DIR = (
    Path(__file__).parents[3] / "_cli" / "fixtures" / "marimo_pair_v0_0_19"
)


@with_session(PAIR_SESSION_ID)
def test_version_and_session_response_shapes(client: TestClient) -> None:
    session = get_session_manager(client).get_session(PAIR_SESSION_ID)
    assert session is not None
    session.app_file_manager.filename = "notebooks/demo.py"

    version = client.get("/api/version", headers=token_header())
    assert version.status_code == 200
    assert version.headers["content-type"].startswith("text/plain")
    assert version.text == __version__

    sessions = client.get("/api/sessions", headers=token_header())
    assert sessions.status_code == 200
    assert sessions.json() == {
        "pair-session": {
            "filename": "notebooks/demo.py",
            "path": str(Path("notebooks/demo.py").absolute()),
        }
    }


@with_session(PAIR_SESSION_ID)
def test_execution_request_and_sse_response(client: TestClient) -> None:
    session = get_session_manager(client).get_session(PAIR_SESSION_ID)
    assert session is not None

    request_body = json.loads(
        (FIXTURE_DIR / "execute-request.json").read_text()
    )
    success_fixture = (FIXTURE_DIR / "execute-success.sse").read_text()
    stdout_record, done_record = success_fixture.split("\n\n", maxsplit=1)
    stdout_record = f"{stdout_record}\n\n"
    captured_commands: list[ExecuteScratchpadCommand] = []

    def capture(command: object, from_consumer_id: object) -> None:
        del from_consumer_id
        if isinstance(command, ExecuteScratchpadCommand):
            captured_commands.append(command)

    async def stream_stdout(
        listener: ScratchCellListener,
    ) -> AsyncGenerator[str, None]:
        del listener
        yield stdout_record

    with (
        patch.object(session, "put_control_request", side_effect=capture),
        patch.object(ScratchCellListener, "stream", stream_stdout),
        patch(
            "marimo._server.scratchpad.build_done_event",
            return_value=done_record,
        ),
    ):
        response = client.post(
            "/api/kernel/execute",
            headers=PAIR_HEADERS,
            json=request_body,
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text == success_fixture
    assert len(captured_commands) == 1
    assert captured_commands[0].code == "print('hello')"


def test_pair_routes_require_authentication(client: TestClient) -> None:
    version = client.get("/api/version")
    sessions = client.get("/api/sessions")
    execution = client.post(
        "/api/kernel/execute",
        headers={"Marimo-Session-Id": PAIR_SESSION_ID},
        json={"code": "print('hello')"},
    )

    assert version.status_code == 401
    assert sessions.status_code == 401
    assert execution.status_code == 401
