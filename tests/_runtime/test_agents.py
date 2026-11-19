# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

import marimo as mo


@pytest.mark.parametrize("send", [mo.agents.send, mo.agents.start_send])
def test_plain_script_has_no_agent_context(send) -> None:
    assert not mo.agents.available()
    with pytest.raises(
        mo.agents.AgentContextUnavailableError,
        match="No marimo context on this thread",
    ):
        mo.agents.list()
    with pytest.raises(mo.agents.AgentContextUnavailableError):
        send(None, to="agent")


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"to": ""}, ValueError),
        ({"to": None}, TypeError),
        ({"timeout": 0}, ValueError),
        ({"timeout": float("nan")}, ValueError),
        ({"timeout": True}, TypeError),
        ({"sender": "bad\nlabel"}, ValueError),
        ({"sender": "x" * 65}, ValueError),
        ({"sender": 1}, TypeError),
    ],
)
@pytest.mark.parametrize("send", [mo.agents.send, mo.agents.start_send])
def test_bad_call_arguments(
    kwargs: dict, error: type[Exception], send
) -> None:
    with pytest.raises(error):
        send(None, **{"to": "agent", **kwargs})


@pytest.mark.parametrize(
    "message",
    [
        {1: "value"},
        {"value": float("inf")},
        {"value": object()},
        "x" * (4 * 1024 * 1024),
    ],
)
@pytest.mark.parametrize("send", [mo.agents.send, mo.agents.start_send])
def test_invalid_message_is_a_call_error(message: object, send) -> None:
    with pytest.raises((TypeError, ValueError)):
        send(message, to="agent")


def test_transport_reports_no_server() -> None:
    import socket

    from marimo._messaging.agents import AgentConnection
    from marimo._runtime.agent_messaging import call

    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
        config = AgentConnection(f"http://127.0.0.1:{port}", "", "")
        with pytest.raises(mo.agents.AgentError, match="Could not connect"):
            call(config, "list", timeout=1)


@pytest.mark.parametrize("status", [400, 409, 413, 503])
def test_transport_returns_call_rejection(status: int) -> None:
    from marimo._messaging.agents import AgentConnection
    from marimo._runtime.agent_messaging import call
    from tests._http import http_test_server

    with http_test_server() as endpoint:
        endpoint.status = status
        endpoint.body = b'{"detail":"Call exceeds a limit"}'
        config = AgentConnection(endpoint.url, "", "")
        with pytest.raises(
            mo.agents.AgentError, match="Call exceeds a limit"
        ) as error:
            call(config, "send", timeout=1, message_id="id", to="agent")
        assert not isinstance(error.value, mo.agents.SendOutcomeUnknownError)


@pytest.mark.parametrize(
    "start", [mo.agents.start_send, mo.agents.start_broadcast]
)
def test_future_request_errors(executing_kernel, start) -> None:
    from marimo._messaging.agents import AgentConnection
    from tests._http import http_test_server

    with http_test_server() as endpoint:
        endpoint.status = 503
        endpoint.body = b'{"detail":"Call exceeds a limit"}'
        executing_kernel.agent_messaging = AgentConnection(
            endpoint.url, "", ""
        )
        kwargs = {"to": "agent"} if start is mo.agents.start_send else {}
        future = start(None, **kwargs)
        with pytest.raises(mo.agents.AgentError, match="Call exceeds a limit"):
            future.result(timeout=5)
        assert isinstance(future.exception(), mo.agents.AgentError)


def test_future_send_starts_outside_a_cell(k) -> None:
    from marimo._messaging.agents import AgentConnection
    from tests._http import http_test_server

    with http_test_server() as endpoint:
        endpoint.status = 503
        endpoint.body = b'{"detail":"Call exceeds a limit"}'
        k.agent_messaging = AgentConnection(endpoint.url, "", "")
        future = mo.agents.start_broadcast(None)
        with pytest.raises(mo.agents.AgentError, match="Call exceeds a limit"):
            future.result(timeout=5)


def test_future_sends_keep_no_cell_state(executing_kernel) -> None:
    from marimo._messaging.agents import AgentConnection
    from marimo._runtime.context import get_context
    from tests._http import http_test_server

    registry = get_context().cell_lifecycle_registry.registry
    before = {cell: len(items) for cell, items in registry.items()}
    with http_test_server() as endpoint:
        endpoint.status = 503
        endpoint.body = b'{"detail":"Call exceeds a limit"}'
        executing_kernel.agent_messaging = AgentConnection(
            endpoint.url, "", ""
        )
        for _ in range(3):
            mo.agents.start_broadcast(None).exception(timeout=5)
    assert {cell: len(items) for cell, items in registry.items()} == before
