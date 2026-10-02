# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import uvicorn
from starlette.testclient import TestClient

from marimo._config.manager import MarimoConfigManager
from marimo._messaging.participants import HandoffEvent
from marimo._server.config import StarletteServerStateInit
from marimo._server.main import create_starlette_app
from marimo._types.ids import SessionId
from tests._server.conftest import join_kernel_thread_tasks
from tests._server.mocks import (
    get_mock_session_manager,
    get_session_manager,
    get_starlette_server_state_init,
    token_header,
    with_session,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator

    from marimo._config.manager import UserConfigManager

SESSION_ID = SessionId("session-123")
PAIR_PREVIEW_ENV = "MARIMO_PAIR_NEXT"


@pytest.fixture
def client(user_config_manager: UserConfigManager) -> Iterator[TestClient]:
    with patch.dict(os.environ, {PAIR_PREVIEW_ENV: "1"}):
        app = create_starlette_app(base_url="", enable_auth=True)
        StarletteServerStateInit(
            port=1234,
            host="localhost",
            base_url="",
            asset_url=None,
            headless=False,
            quiet=False,
            session_manager=get_mock_session_manager(),
            config_manager=MarimoConfigManager(user_config_manager),
            remote_url=None,
            mcp_server_enabled=False,
            skew_protection=False,
            enable_auth=True,
        ).apply(app.state)
        server = uvicorn.Server(uvicorn.Config(app))
        server.servers = []
        app.state.server = server
        test_client = TestClient(app)

        yield test_client

        asyncio.run(join_kernel_thread_tasks(app.state.session_manager))


def _participant_headers(
    client: TestClient, participant_id: str = "p1"
) -> dict[str, str]:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session is not None
    return {
        "Marimo-Stable-Session-Id": session.stable_id,
        "Marimo-Participant-Id": participant_id,
        **token_header("fake-token"),
    }


def _participant_metadata() -> dict[str, object]:
    return {
        "kind": "agent",
        "harness": {"id": "pi", "displayName": "Pi"},
    }


def _handoff_payload(value: str = "RuntimeError") -> dict[str, object]:
    return {
        "cellId": "cell-1",
        "error": value,
        "code": "raise RuntimeError()",
        "traceback": "Traceback\nRuntimeError",
        "consoleTail": [],
        "note": None,
    }


@with_session(SESSION_ID)
def test_attach_handoff_read_and_detach(client: TestClient) -> None:
    participant_headers = _participant_headers(client)
    session_headers = {
        "Marimo-Stable-Session-Id": participant_headers[
            "Marimo-Stable-Session-Id"
        ],
        **token_header("fake-token"),
    }

    attached = client.post(
        "/api/participants/attach",
        headers=participant_headers,
        json=_participant_metadata(),
    )
    handed_off = client.post(
        "/api/participants/handoff",
        headers=session_headers,
        json=_handoff_payload(),
    )
    events = client.get(
        "/api/participants/events?limit=1", headers=participant_headers
    )
    detached = client.post(
        "/api/participants/detach", headers=participant_headers
    )

    assert attached.status_code == 200, attached.text
    assert attached.json() == {
        "participantId": "p1",
        "cursor": 0,
        "attached": True,
        "recordCreated": True,
        "kind": "agent",
        "harness": {"id": "pi", "displayName": "Pi"},
    }
    assert handed_off.status_code == 200, handed_off.text
    assert handed_off.json() == {"seq": 1}
    assert events.status_code == 200, events.text
    assert events.json()["cursor"] == 1
    assert events.json()["remaining"] == 0
    assert events.json()["events"][0]["error"] == "RuntimeError"
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session is not None
    presence = session.session_view.participant_presence
    assert presence is not None
    assert presence.harness.id == "pi"
    assert presence.harness.display_name == "Pi"
    assert detached.status_code == 200, detached.text
    assert detached.json() == {"participantId": "p1", "attached": False}


@with_session(SESSION_ID)
def test_events_since_replays_after_default_cursor_advances(
    client: TestClient,
) -> None:
    participant_headers = _participant_headers(client)
    attached = client.post(
        "/api/participants/attach",
        headers=participant_headers,
        json=_participant_metadata(),
    )
    assert attached.status_code == 200, attached.text
    handed_off = client.post(
        "/api/participants/handoff",
        headers={
            "Marimo-Stable-Session-Id": participant_headers[
                "Marimo-Stable-Session-Id"
            ],
            **token_header("fake-token"),
        },
        json=_handoff_payload(),
    )
    assert handed_off.status_code == 200, handed_off.text

    first = client.get("/api/participants/events", headers=participant_headers)
    assert first.status_code == 200, first.text
    assert [event["seq"] for event in first.json()["events"]] == [1]

    for _ in range(3):
        replay = client.get(
            "/api/participants/events?since=0",
            headers=participant_headers,
        )
        assert replay.status_code == 200, replay.text
        assert [event["seq"] for event in replay.json()["events"]] == [1]
        assert replay.json()["cursor"] == 1

    pending = client.get(
        "/api/participants/events", headers=participant_headers
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["events"] == []


@with_session(SESSION_ID)
def test_attach_reports_record_creation_and_keeps_harness(
    client: TestClient,
) -> None:
    headers = _participant_headers(client)
    first = client.post(
        "/api/participants/attach",
        headers=headers,
        json=_participant_metadata(),
    )
    second = client.post("/api/participants/attach", headers=headers)
    resumed = client.get("/api/participants/events", headers=headers)

    assert first.status_code == 200, first.text
    assert first.json()["recordCreated"] is True
    assert second.status_code == 200, second.text
    assert second.json()["recordCreated"] is False
    assert second.json()["harness"] == {
        "id": "pi",
        "displayName": "Pi",
    }
    assert resumed.status_code == 200, resumed.text
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session is not None
    assert session.session_view.participant_presence is not None
    assert session.session_view.participant_presence.harness.id == "pi"


@with_session(SESSION_ID)
def test_events_reject_unknown_participant(client: TestClient) -> None:
    response = client.get(
        "/api/participants/events", headers=_participant_headers(client)
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Unknown participant ID: p1."}


@with_session(SESSION_ID)
def test_handoff_requires_live_participant(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session is not None

    response = client.post(
        "/api/participants/handoff",
        headers={
            "Marimo-Stable-Session-Id": session.stable_id,
            **token_header("fake-token"),
        },
        json=_handoff_payload(),
    )

    assert response.status_code == 409, response.text
    assert response.json() == {
        "detail": "No participant is attached to this session."
    }


@with_session(SESSION_ID)
def test_participant_route_requires_identity_headers(
    client: TestClient,
) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session is not None

    missing_participant = client.post(
        "/api/participants/attach",
        headers={
            "Marimo-Stable-Session-Id": session.stable_id,
            **token_header("fake-token"),
        },
        json=_participant_metadata(),
    )
    missing_stable_session = client.post(
        "/api/participants/attach",
        headers={
            "Marimo-Participant-Id": "p1",
            **token_header("fake-token"),
        },
        json=_participant_metadata(),
    )

    assert missing_participant.status_code == 400
    assert missing_participant.json() == {
        "detail": "Missing Marimo-Participant-Id header."
    }
    assert missing_stable_session.status_code == 400
    assert missing_stable_session.json() == {
        "detail": ("Marimo-Participant-Id requires Marimo-Stable-Session-Id.")
    }


@with_session(SESSION_ID)
def test_attach_validates_participant_metadata(client: TestClient) -> None:
    metadata = _participant_metadata()
    metadata["kind"] = "robot"

    response = client.post(
        "/api/participants/attach",
        headers=_participant_headers(client),
        json=metadata,
    )

    assert response.status_code == 400, response.text


@with_session(SESSION_ID)
def test_attach_rejects_control_characters_in_harness_name(
    client: TestClient,
) -> None:
    metadata = _participant_metadata()
    metadata["harness"] = {"id": "pi", "displayName": "Pi\nAgent"}

    response = client.post(
        "/api/participants/attach",
        headers=_participant_headers(client),
        json=metadata,
    )

    assert response.status_code == 400, response.text


@with_session(SESSION_ID)
def test_handoff_enforces_payload_cap(client: TestClient) -> None:
    participant_headers = _participant_headers(client)
    attached = client.post(
        "/api/participants/attach",
        headers=participant_headers,
        json=_participant_metadata(),
    )
    assert attached.status_code == 200, attached.text

    response = client.post(
        "/api/participants/handoff",
        headers={
            "Marimo-Stable-Session-Id": participant_headers[
                "Marimo-Stable-Session-Id"
            ],
            **token_header("fake-token"),
        },
        json=_handoff_payload("x" * (256 * 1024)),
    )

    assert response.status_code == 413, response.text
    assert response.json() == {
        "detail": "Handoff payload exceeds the configured limit."
    }


@with_session(SESSION_ID)
def test_events_validate_query_parameters(client: TestClient) -> None:
    attached = client.post(
        "/api/participants/attach",
        headers=_participant_headers(client),
        json=_participant_metadata(),
    )
    assert attached.status_code == 200, attached.text
    response = client.get(
        "/api/participants/events?since=-1",
        headers=_participant_headers(client),
    )

    assert response.status_code == 400, response.text
    assert response.json() == {
        "detail": "since must be a non-negative integer."
    }


@with_session(SESSION_ID)
def test_event_stream_uses_sse_framing(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session is not None
    headers = _participant_headers(client)
    attached = client.post(
        "/api/participants/attach",
        headers=headers,
        json=_participant_metadata(),
    )
    assert attached.status_code == 200, attached.text
    event = HandoffEvent(
        seq=1,
        created_at=0,
        cell_id="cell-1",
        error="RuntimeError",
        code="raise RuntimeError()",
        traceback="Traceback\nRuntimeError",
    )

    async def finite_stream(
        participant_id: str,  # noqa: ARG001
    ) -> AsyncGenerator[HandoffEvent | None, None]:
        yield event

    with patch.object(session.participants, "stream_events", finite_stream):
        response = client.get(
            "/api/participants/events/stream", headers=headers
        )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.startswith("event: handoff\n")
    assert '"error":"RuntimeError"' in response.text


def test_participant_routes_are_absent_when_preview_is_off() -> None:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key != PAIR_PREVIEW_ENV
    }
    with patch.dict(os.environ, environment, clear=True):
        app = create_starlette_app(base_url="", enable_auth=True)
    get_starlette_server_state_init().apply(app.state)
    off_client = TestClient(app)

    response = off_client.get(
        "/api/participants/events", headers=token_header("fake-token")
    )

    assert response.status_code == 404
    asyncio.run(app.state.session_manager.shutdown())
