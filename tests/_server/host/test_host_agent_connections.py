# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from marimo._core import backend as be
from marimo._core.host import Host
from marimo._messaging.notification import (
    FunctionCallResultNotification,
    HumanReadableStatus,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._server.host.agent_connections import AgentConnections
from marimo._session.events import SessionEventBus
from tests._core.conftest import ScriptedBackend, add_notebook, project, record


def session_stub():
    session = MagicMock()
    bus = SessionEventBus()
    extensions = []

    @contextmanager
    def scoped(extension):
        extensions.append(extension)
        extension.on_attach(session, bus)
        try:
            yield extension
        finally:
            extension.on_detach()
            extensions.remove(extension)

    session.scoped.side_effect = scoped
    return session, bus, extensions


def acknowledge(session, bus, *, found=True, status="ok"):
    command = session.put_control_request.call_args.args[0]
    bus.emit_notification_sent(
        session,
        serialize_kernel_message(
            FunctionCallResultNotification(
                command.function_call_id,
                None,
                HumanReadableStatus(status),
                found,
            )
        ),
    )


@pytest.fixture
async def setup():
    host = Host(operations=[])
    host.update_project(project())
    notebook = await add_notebook(host, record(), ScriptedBackend())
    connections = AgentConnections(host)
    session, bus, extensions = session_stub()
    yield host, notebook, connections, session, bus, extensions
    connections.close()


async def test_initial_and_later_snapshot(setup) -> None:
    _, notebook, connections, session, bus, _ = setup
    connections.subscribe(notebook, session, "observer")
    assert session.put_control_request.call_args.args[0].args == {
        "revision": 1,
        "agents": [],
    }
    acknowledge(session, bus)
    notebook.attach(kind="agent", identity="agent")
    assert session.put_control_request.call_count == 2
    assert session.put_control_request.call_args.args[0].args == {
        "revision": 2,
        "agents": [{"id": "agent", "name": None}],
    }


async def test_busy_churn_retains_one_in_flight_and_latest_state(
    setup,
) -> None:
    _, notebook, connections, session, bus, _ = setup
    connections.subscribe(notebook, session, "observer")
    for i in range(1000):
        attachment = notebook.attach(kind="agent", identity=str(i))
        notebook.detach(attachment.id)
    notebook.attach(kind="agent", identity="final")
    assert session.put_control_request.call_count == 1
    assert len(connections._calls) == len(connections._subscriptions) == 1
    acknowledge(session, bus)
    assert session.put_control_request.call_count == 2
    assert session.put_control_request.call_args.args[0].args == {
        "revision": 2,
        "agents": [{"id": "final", "name": None}],
    }
    acknowledge(session, bus)
    assert not connections._calls
    assert session.put_control_request.call_count == 2


async def test_duplicate_streams_and_selected_name(setup) -> None:
    _, notebook, connections, session, bus, _ = setup
    first = notebook.attach(kind="agent", identity="same", name="Old")
    second = notebook.attach(kind="agent", identity="same", name="New")
    connections.subscribe(notebook, session, "observer")
    acknowledge(session, bus)
    notebook.detach(second.id)
    assert session.put_control_request.call_args.args[0].args["agents"] == [
        {"id": "same", "name": "Old"}
    ]
    acknowledge(session, bus)
    duplicate = notebook.attach(kind="agent", identity="same", name="Old")
    notebook.detach(first.id)
    assert session.put_control_request.call_count == 2
    notebook.detach(duplicate.id)
    assert session.put_control_request.call_args.args[0].args["agents"] == []


async def test_independent_subscribers_and_callback_failure(setup) -> None:
    _, notebook, connections, session, bus, extensions = setup
    connections.subscribe(notebook, session, "first")
    connections.subscribe(notebook, session, "second")
    assert len(extensions) == 1
    acknowledge(session, bus, status="error")
    notebook.attach(kind="agent", identity="agent")
    assert session.put_control_request.call_count == 3
    connections.unsubscribe(session, "first")
    assert len(extensions) == 1
    connections.unsubscribe(session, "second")
    assert not extensions
    assert not connections._subscriptions
    assert not connections._calls
    assert not connections._sessions


async def test_disposal_and_stale_ack_cannot_restore_observer(setup) -> None:
    _, notebook, connections, session, bus, extensions = setup
    connections.subscribe(notebook, session, "observer")
    command = session.put_control_request.call_args.args[0]
    connections.unsubscribe(session, "observer")
    connections.unsubscribe(session, "observer")
    bus.emit_notification_sent(
        session,
        serialize_kernel_message(
            FunctionCallResultNotification(
                command.function_call_id, None, HumanReadableStatus("ok"), True
            )
        ),
    )
    notebook.attach(kind="agent")
    assert session.put_control_request.call_count == 1
    assert not extensions
    assert not connections._subscriptions
    assert not connections._calls


async def test_missing_function_releases_server_resources(setup) -> None:
    _, notebook, connections, session, bus, extensions = setup
    connections.subscribe(notebook, session, "observer")
    acknowledge(session, bus, found=False)
    assert not extensions
    assert not connections._subscriptions
    assert not connections._calls
    assert not connections._sessions


async def test_session_detach_releases_observers(setup) -> None:
    _, notebook, connections, session, _, extensions = setup
    connections.subscribe(notebook, session, "one")
    connections.subscribe(notebook, session, "two")
    extensions[0].on_detach()
    assert not extensions
    assert not connections._subscriptions
    assert not connections._calls
    assert not connections._sessions


async def test_session_and_notebook_isolation(setup) -> None:
    host, notebook, connections, session, bus, _ = setup
    other = await add_notebook(host, record("other.py"), ScriptedBackend())
    other_session, other_bus, _ = session_stub()
    connections.subscribe(notebook, session, "one")
    connections.subscribe(other, other_session, "two")
    with pytest.raises(ValueError, match="another runtime"):
        connections.subscribe(other, other_session, "one")
    acknowledge(session, bus)
    acknowledge(other_session, other_bus)
    connections.unsubscribe(other_session, "one")
    notebook.attach(kind="agent", identity="first")
    assert session.put_control_request.call_count == 2
    assert other_session.put_control_request.call_count == 1
    other.attach(kind="agent", identity="other")
    assert other_session.put_control_request.call_args.args[0].args[
        "agents"
    ] == [{"id": "other", "name": None}]


async def test_runtime_replacement_does_not_restore_callbacks(setup) -> None:
    _, notebook, connections, session, _, extensions = setup
    runtime = notebook.adopt(lambda _: None)
    connections.subscribe(notebook, session, "old")
    old_command = session.put_control_request.call_args.args[0]
    notebook.observe(be.Exited(runtime.id))
    assert not extensions
    assert not connections._subscriptions
    notebook.adopt(lambda _: None)
    replacement, replacement_bus, _ = session_stub()
    notebook.attach(kind="agent", identity="live")
    connections.subscribe(notebook, replacement, "new")
    connections.on_notification_sent(
        session,
        serialize_kernel_message(
            FunctionCallResultNotification(
                old_command.function_call_id,
                None,
                HumanReadableStatus("ok"),
                True,
            )
        ),
    )
    assert replacement.put_control_request.call_count == 1
    assert replacement.put_control_request.call_args.args[0].args[
        "agents"
    ] == [{"id": "live", "name": None}]
    acknowledge(replacement, replacement_bus)
    assert not connections._calls


async def test_notebook_removal_releases_resources(setup) -> None:
    host, notebook, connections, session, _, extensions = setup
    connections.subscribe(notebook, session, "observer")
    host.remove_notebook(notebook.id)
    assert not extensions
    assert not connections._subscriptions
    assert not connections._calls
    assert not connections._sessions


async def test_runtime_stop_releases_resources_before_exit(setup) -> None:
    _, notebook, connections, session, _, extensions = setup
    notebook.adopt(lambda _: None)
    connections.subscribe(notebook, session, "observer")
    notebook.stop()
    assert not extensions
    assert not connections._subscriptions
    assert not connections._calls
    assert not connections._sessions
