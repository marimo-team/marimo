# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import socket
import threading
import time
from typing import TYPE_CHECKING

import msgspec
import pytest

import marimo as mo
from marimo._messaging.agents import (
    AgentConnection,
    RecipientResult,
    SendResult,
)
from marimo._runtime.agent_messaging import call
from marimo._runtime.context import get_context
from marimo._runtime.context.types import teardown_context

if TYPE_CHECKING:
    from tests._http import HTTPEndpoint


@pytest.fixture
def endpoint(
    http_endpoint: HTTPEndpoint,
) -> tuple[AgentConnection, HTTPEndpoint]:
    http_endpoint.body = msgspec.json.encode(
        SendResult((RecipientResult("agent", "submitted"),))
    )
    http_endpoint.headers["Location"] = "/redirect-target"
    return (
        AgentConnection(
            f"{http_endpoint.url}/base/api/pair/notebooks/sess_one",
            "private-edit-token",
            "private-skew-token",
        ),
        http_endpoint,
    )


def test_public_calls_use_the_editor_endpoints(k, endpoint) -> None:
    config, state = endpoint
    k.agent_messaging = config
    state.body = b'[{"id":"agent","name":null}]'
    assert mo.agents.list() == (mo.agents.AgentInfo("agent", None),)
    state.body = msgspec.json.encode(
        SendResult((RecipientResult("agent", "submitted"),))
    )
    assert mo.agents.send({"opaque": [1, None]}, to="agent") == SendResult(
        (RecipientResult("agent", "submitted"),)
    )
    assert mo.agents.broadcast(False) == SendResult(
        (RecipientResult("agent", "submitted"),)
    )
    assert [(r.method, r.path) for r in state.requests] == [
        ("GET", "/base/api/pair/notebooks/sess_one/agents"),
        ("POST", "/base/api/pair/notebooks/sess_one/messages"),
        ("POST", "/base/api/pair/notebooks/sess_one/messages"),
    ]
    bodies = []
    for request in state.requests:
        assert (
            request.headers.get("Authorization"),
            request.headers.get("Marimo-Server-Token"),
        ) == (
            "Bearer private-edit-token",
            "private-skew-token",
        )
        body = msgspec.json.decode(request.body) if request.body else None
        if body is not None:
            assert 0 < body.pop("timeout") <= 30
        bodies.append(body)
    assert bodies == [
        None,
        {"message": {"opaque": [1, None]}, "to": "agent", "broadcast": False},
        {"message": False, "to": None, "broadcast": True},
    ]
    assert "private-edit-token" not in repr(config)
    assert "private-skew-token" not in repr(config)


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        (409, "unavailable", mo.agents.MessagingUnavailableError),
        (409, "no-agents", mo.agents.NoAgentsConnectedError),
        (503, "failed", mo.agents.AgentMessagingError),
        (400, "invalid-argument", mo.agents.AgentMessagingError),
    ],
)
def test_typed_endpoint_errors(k, endpoint, status, code, expected) -> None:
    config, state = endpoint
    k.agent_messaging = config
    state.status = status
    state.body = msgspec.json.encode(
        {"code": code, "detail": "Definite failure"}
    )
    with pytest.raises(expected, match="Definite failure"):
        mo.agents.broadcast(None)
    assert len(state.requests) == 1


@pytest.mark.parametrize("status", [200, 302, 409, 500, 503])
def test_ambiguous_or_malformed_responses_are_unknown(
    k, endpoint, status
) -> None:
    config, state = endpoint
    k.agent_messaging = config
    state.status = status
    state.body = b"{}"
    with pytest.raises(mo.agents.SendOutcomeUnknownError):
        mo.agents.send(None, to="agent")
    assert len(state.requests) == 1


def test_timeout_never_retries(k, endpoint) -> None:
    config, state = endpoint
    k.agent_messaging = config
    state.delay = 0.2
    started = time.monotonic()
    with pytest.raises(mo.agents.SendOutcomeUnknownError):
        mo.agents.send(None, to="agent", timeout=0.04)
    assert time.monotonic() - started < 0.2
    assert len(state.requests) == 1


def test_truncated_http_response_is_unknown(k, endpoint) -> None:
    config, state = endpoint
    k.agent_messaging = config
    state.content_length = len(state.body) + 10
    with pytest.raises(mo.agents.SendOutcomeUnknownError):
        mo.agents.send(None, to="agent")
    assert len(state.requests) == 1


@pytest.mark.parametrize("status", [401, 403, 404, 405])
@pytest.mark.parametrize("truncated", [False, True])
def test_unavailable_endpoint_is_definite_even_with_a_truncated_body(
    k, endpoint, status, truncated
) -> None:
    config, state = endpoint
    k.agent_messaging = config
    state.status = status
    if truncated:
        state.content_length = len(state.body) + 10
    with pytest.raises(mo.agents.MessagingUnavailableError):
        mo.agents.send(None, to="agent")
    assert len(state.requests) == 1


def test_oversized_response_is_unknown(k, endpoint, monkeypatch) -> None:
    config, state = endpoint
    k.agent_messaging = config
    monkeypatch.setattr(
        "marimo._runtime.agent_messaging._MAX_RESPONSE_BYTES", 2
    )
    with pytest.raises(mo.agents.SendOutcomeUnknownError):
        mo.agents.send(None, to="agent")
    assert len(state.requests) == 1


def test_connection_failure_is_unavailable() -> None:
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
    config = AgentConnection(f"http://127.0.0.1:{port}/session", "", "")
    with pytest.raises(mo.agents.MessagingUnavailableError, match="connect"):
        call(config, "send", timeout=1, message=None, to="agent")


def test_listing_failure_does_not_claim_possible_delivery(k, endpoint) -> None:
    config, state = endpoint
    k.agent_messaging = config
    state.body = b"not JSON"
    with pytest.raises(mo.agents.AgentMessagingError) as error:
        mo.agents.list()
    assert not isinstance(error.value, mo.agents.SendOutcomeUnknownError)


def test_context_aware_callback_needs_no_cell(k, endpoint) -> None:
    config, _ = endpoint
    k.agent_messaging = config
    context = get_context()
    assert context.cell_id is None
    results = []

    def callback() -> None:
        with context.install():
            results.append(mo.agents.send(None, to="agent"))

    worker = threading.Thread(target=callback)
    worker.start()
    worker.join(timeout=2)
    assert results == [SendResult((RecipientResult("agent", "submitted"),))]


@pytest.mark.parametrize(
    "operation",
    [
        mo.agents.list,
        lambda: mo.agents.send(None, to="agent"),
        lambda: mo.agents.broadcast(None),
    ],
)
def test_unbound_context_is_unavailable(operation) -> None:
    teardown_context()
    with pytest.raises(mo.agents.MessagingUnavailableError):
        operation()


@pytest.mark.usefixtures("run_mode_kernel")
def test_read_mode_is_unavailable() -> None:
    with pytest.raises(mo.agents.MessagingUnavailableError):
        mo.agents.list()


@pytest.mark.parametrize(
    ("args", "error"),
    [
        ({"to": None}, TypeError),
        ({"to": ""}, ValueError),
        ({"to": "a", "timeout": True}, TypeError),
        ({"to": "a", "timeout": 0}, ValueError),
    ],
)
def test_invalid_arguments_fail_before_context_resolution(args, error) -> None:
    with pytest.raises(error):
        mo.agents.send(None, **args)
