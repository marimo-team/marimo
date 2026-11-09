# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import msgspec
import pytest

from marimo._ast.app import App, InternalApp
from marimo._config.manager import get_default_config_manager
from marimo._core import backend as be, protocol
from marimo._messaging.agents import (
    MESSAGE_TYPE,
    SubmissionReport,
)
from marimo._server.host.bridge import SessionBridge
from marimo._server.host.context import HostContext
from marimo._server.workspace import SingleFileWorkspace
from marimo._session.consumer import SessionConsumer
from marimo._session.extensions.extensions import SessionViewExtension
from marimo._session.managers import KernelManagerImpl
from marimo._session.model import ConnectionState, SessionMode
from marimo._session.notebook import AppFileManager
from marimo._session.session import SessionImpl
from marimo._session.state.session_view import SessionView
from marimo._types.ids import ConsumerId, SessionId
from marimo._utils.marimo_path import MarimoPath
from tests._server.mocks import get_session_manager, token_header

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from starlette.testclient import TestClient

    from marimo._core.notebook import Notebook


@pytest.fixture
async def target(
    client: TestClient, tmp_path: Path
) -> AsyncIterator[tuple[SessionImpl, Notebook]]:
    consumer = Mock(spec=SessionConsumer)
    consumer.consumer_id = ConsumerId("browser")
    consumer.connection_state.return_value = ConnectionState.OPEN
    kernel = Mock(spec=KernelManagerImpl)
    kernel.kernel_task = None
    session = SessionImpl(
        session_view=SessionView(),
        initialization_id="notebook.py",
        session_consumer=consumer,
        kernel_manager=kernel,
        app_file_manager=AppFileManager.from_app(InternalApp(App())),
        config_manager=get_default_config_manager(current_path=None),
        ttl_seconds=None,
        extensions=[SessionViewExtension()],
    )
    manager = get_session_manager(client)
    file = tmp_path / "notebook.py"
    file.write_text("import marimo\napp = marimo.App()\n")
    session.app_file_manager.filename = str(file)
    manager.workspace = SingleFileWorkspace.from_path(MarimoPath(file))
    manager._repository.add_sync(SessionId("browser"), session)
    bridge = SessionBridge(manager)
    await bridge.open()
    notebook = bridge.notebook_for_session(session)
    assert notebook is not None
    client.app.state.host_context = HostContext(bridge, "host-token", 2718)
    try:
        yield session, notebook
    finally:
        client.app.state.host_context = None
        bridge.close()
        session.close()


def path(session: SessionImpl, operation: str) -> str:
    return f"/api/pair/notebooks/{session.stable_id}/{operation}"


def test_agent_listing_preserves_logical_recipients(
    client: TestClient, target: tuple[SessionImpl, Notebook]
) -> None:
    session, notebook = target
    notebook.attach(kind="agent", identity="codex", name="Codex")
    notebook.attach(kind="agent", identity="codex", name="Codex")
    notebook.attach(kind="agent", identity="claude", name="Claude")
    notebook.attach(kind="client")
    response = client.get(
        path(session, "agents"), headers=token_header("fake-token")
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert sorted(response.json(), key=lambda agent: agent["id"]) == [
        {"id": "claude", "name": "Claude"},
        {"id": "codex", "name": "Codex"},
    ]


@pytest.mark.parametrize(
    "payload", [{"cell": "x", "text": "λ"}, [1, "a"], "hello", 42, True, None]
)
def test_message_is_opaque_and_only_targets_the_selected_agent(
    client: TestClient, target: tuple[SessionImpl, Notebook], payload: object
) -> None:
    session, notebook = target
    attachment = notebook.attach(kind="agent", identity="codex", name="Codex")
    notebook.attach(kind="agent", identity="claude", name="Claude")
    events = []
    messages = client.app.state.host_context.agents
    key = messages.register(notebook, attachment.id)

    def submit(event) -> None:
        data = event.event.data.custom.data
        messages.report(
            notebook.id,
            SubmissionReport(
                data["attachment_id"], data["attempt_id"], "submitted"
            ),
            key,
        )

    client.app.state.host_context.bridge.host.subscribe(
        submit, notebook_id=notebook.id, types={"custom"}
    )
    client.app.state.host_context.bridge.host.subscribe(
        events.append, notebook_id=notebook.id, types={"custom"}
    )
    response = client.post(
        path(session, "messages"),
        content=msgspec.json.encode({"message": payload, "to": "codex"}),
        headers=token_header("fake-token"),
    )
    assert (response.status_code, response.json()) == (
        200,
        {
            "recipients": [
                {"agent_id": "codex", "status": "submitted", "detail": None}
            ]
        },
    )
    assert len(events) == 1
    event = events[0].event
    assert isinstance(event, protocol.CustomEvent)
    assert event.data.custom.type == MESSAGE_TYPE
    assert event.data.custom.data["message"] == payload
    assert event.data.custom.data["attachment_id"] == attachment.id


@pytest.mark.parametrize("client_attached", [False, True])
def test_message_requires_an_agent(
    client: TestClient,
    target: tuple[SessionImpl, Notebook],
    client_attached: bool,
) -> None:
    session, notebook = target
    if client_attached:
        notebook.attach(kind="client")
    response = client.post(
        path(session, "messages"),
        json={"message": None, "broadcast": True},
        headers=token_header("fake-token"),
    )
    assert (response.status_code, response.json()) == (
        409,
        {"code": "no-agents", "detail": "No agents are connected"},
    )


def test_no_host_notebook(
    client: TestClient, target: tuple[SessionImpl, Notebook]
) -> None:
    session, _ = target
    client.app.state.host_context = None
    response = client.post(
        path(session, "messages"),
        json={"message": None, "broadcast": True},
        headers=token_header("fake-token"),
    )
    assert response.status_code == 409
    response = client.get(
        path(session, "agents"), headers=token_header("fake-token")
    )
    assert (response.status_code, response.json()["code"]) == (
        409,
        "unavailable",
    )
    response = client.post(
        path(session, "attachments/detach"),
        json={"attachment_id": "missing"},
        headers=token_header("fake-token"),
    )
    assert response.status_code == 204


def test_invalid_message_precedes_notebook_availability(
    client: TestClient, target: tuple[SessionImpl, Notebook]
) -> None:
    session, _ = target
    client.app.state.host_context = None
    response = client.post(
        path(session, "messages"),
        content=b"{",
        headers=token_header("fake-token"),
    )
    assert (response.status_code, response.json()["code"]) == (
        400,
        "invalid-argument",
    )


def test_detach_removes_only_the_selected_attachment(
    client: TestClient, target: tuple[SessionImpl, Notebook]
) -> None:
    session, notebook = target
    first = notebook.attach(kind="agent", identity="same")
    second = notebook.attach(kind="agent", identity="same")
    response = client.post(
        path(session, "attachments/detach"),
        json={"attachment_id": first.id},
        headers=token_header("fake-token"),
    )
    assert (response.status_code, notebook.attachments, session._closed) == (
        204,
        [second],
        False,
    )
    response = client.post(
        path(session, "attachments/detach"),
        json={"attachment_id": first.id},
        headers=token_header("fake-token"),
    )
    assert response.status_code == 204


@pytest.mark.parametrize(
    "body",
    [b"{", b"null", b"{}", b'{"attachment_id": 1}', b'{"attachment_id": ""}'],
)
def test_invalid_detach_body(
    client: TestClient, target: tuple[SessionImpl, Notebook], body: bytes
) -> None:
    session, _ = target
    assert (
        client.post(
            path(session, "attachments/detach"),
            content=body,
            headers=token_header("fake-token"),
        ).status_code
        == 400
    )


@pytest.mark.parametrize(
    "body",
    [
        b"{",
        b"[]",
        b'{"message":null,"to":1}',
        b'{"message":null,"broadcast":"true"}',
        b'{"message":null,"broadcast":true,"timeout":"1"}',
        b'{"message":null}',
        b'{"message":null,"to":"codex","broadcast":true}',
    ],
)
def test_invalid_message_json(
    client: TestClient, target: tuple[SessionImpl, Notebook], body: bytes
) -> None:
    session, _ = target
    response = client.post(
        path(session, "messages"),
        content=body,
        headers=token_header("fake-token"),
    )
    assert (response.status_code, response.json()) == (
        400,
        {
            "code": "invalid-argument",
            "detail": "Invalid agent message request.",
        },
    )


@pytest.mark.parametrize(
    "operation", ["messages", "attachments/detach", "agents/subscriptions"]
)
def test_missing_session(client: TestClient, operation: str) -> None:
    assert (
        client.post(
            f"/api/pair/notebooks/missing/{operation}",
            json={},
            headers=token_header("fake-token"),
        ).status_code
        == 404
    )


def test_agent_listing_requires_a_live_session(client: TestClient) -> None:
    response = client.get(
        "/api/pair/notebooks/missing/agents",
        headers=token_header("fake-token"),
    )
    assert (response.status_code, response.json()["code"]) == (
        404,
        "unavailable",
    )


def test_pair_events_route_is_removed(
    client: TestClient, target: tuple[SessionImpl, Notebook]
) -> None:
    session, _ = target
    assert (
        client.get(
            path(session, "events"), headers=token_header("fake-token")
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    ("method", "operation"),
    [
        ("POST", "messages"),
        ("POST", "attachments/detach"),
        ("POST", "agents/subscriptions"),
        ("GET", "agents"),
    ],
)
def test_routes_require_authentication(
    client: TestClient,
    target: tuple[SessionImpl, Notebook],
    method: str,
    operation: str,
) -> None:
    session, notebook = target
    response = client.request(method, path(session, operation))
    assert (response.status_code, notebook.attachments) == (401, [])


@pytest.mark.parametrize(
    ("method", "operation"),
    [
        ("POST", "messages"),
        ("POST", "attachments/detach"),
        ("POST", "agents/subscriptions"),
        ("GET", "agents"),
    ],
)
def test_routes_require_edit_mode(
    client: TestClient,
    target: tuple[SessionImpl, Notebook],
    method: str,
    operation: str,
) -> None:
    session, _ = target
    manager = get_session_manager(client)
    manager.mode = SessionMode.RUN
    headers = token_header(str(manager.auth_token))
    assert client.get("/api/version", headers=headers).status_code == 200
    assert (
        client.request(
            method, path(session, operation), headers=headers
        ).status_code
        == 401
    )


def test_sessions_include_host_notebook_id(
    client: TestClient, target: tuple[SessionImpl, Notebook]
) -> None:
    session, notebook = target
    response = client.get("/api/sessions", headers=token_header("fake-token"))
    assert response.json() == {
        "browser": {
            "session_id": session.stable_id,
            "notebook_id": notebook.id,
            "filename": session.app_file_manager.filename,
            "path": session.app_file_manager.path,
        }
    }


def test_subscription_registration_removal_and_runtime_availability(
    client, target
) -> None:
    session, notebook = target
    connections = client.app.state.host_context.bridge.agent_connections
    body = {"subscription_id": "a" * 32}
    headers = token_header("fake-token")
    url = path(session, "agents/subscriptions")
    assert client.post(url, json=body, headers=headers).status_code == 200
    assert len(connections._subscriptions) == len(connections._calls) == 1
    for _ in range(2):
        assert (
            client.post(
                url, json={**body, "active": False}, headers=headers
            ).status_code
            == 200
        )
    assert not connections._subscriptions
    assert not connections._calls
    assert not connections._sessions
    assert notebook.runtime is not None
    notebook.observe(be.Exited(notebook.runtime.id))
    assert client.post(url, json=body, headers=headers).status_code == 409
    assert not connections._subscriptions


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {"subscription_id": ""},
        {"subscription_id": "g" * 32},
        {"subscription_id": 1},
    ],
)
def test_invalid_subscription_creates_no_resources(
    client, target, body
) -> None:
    session, _ = target
    connections = client.app.state.host_context.bridge.agent_connections
    response = client.post(
        path(session, "agents/subscriptions"),
        content=msgspec.json.encode(body),
        headers=token_header("fake-token"),
    )
    assert response.status_code == 400
    assert not connections._subscriptions
    assert not connections._sessions
