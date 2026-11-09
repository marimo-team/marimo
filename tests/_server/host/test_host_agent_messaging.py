# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from marimo._core import protocol
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.stream import RoutedEvent
from marimo._messaging.agents import (
    MESSAGE_TYPE,
    AgentContextUnavailableError,
    AgentError,
    AgentInfo,
    NoAgentsConnectedError,
    RecipientResult,
    SendResult,
    SubmissionReport,
)
from marimo._server.host.agents import AgentMessaging
from tests._core.conftest import ScriptedBackend, add_notebook, project, record


@pytest.fixture
async def setup() -> tuple[Host, Notebook, AgentMessaging]:
    host = Host(operations=[])
    host.update_project(project())
    notebook = await add_notebook(host, record(), ScriptedBackend())
    return host, notebook, AgentMessaging(host)


def listen(host: Host, notebook: Notebook) -> asyncio.Queue[dict[str, Any]]:
    incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def receive(event: RoutedEvent) -> None:
        assert isinstance(event.event, protocol.CustomEvent)
        custom = event.event.data.custom
        if custom.type == MESSAGE_TYPE:
            incoming.put_nowait(custom.data)

    host.subscribe(receive, notebook_id=notebook.id, types={"custom"})
    return incoming


def reply(data: dict[str, Any], status: str = "submitted") -> SubmissionReport:
    return SubmissionReport(data["attachment_id"], data["attempt_id"], status)  # type: ignore[arg-type]


async def test_logical_listing_and_one_attempt_per_recipient(setup) -> None:
    host, notebook, messages = setup
    notebook.attach(kind="client", name="Browser")
    notebook.attach(kind="agent", identity="same", name="Old")
    latest = notebook.attach(kind="agent", identity="same", name="Agent")
    other = notebook.attach(kind="agent", identity="other", name="Agent")
    keys = {a.id: messages.register(notebook, a.id) for a in (latest, other)}
    assert messages.list(notebook) == (
        AgentInfo("same", "Agent"),
        AgentInfo("other", "Agent"),
    )
    incoming = listen(host, notebook)
    task = asyncio.create_task(
        messages.broadcast(notebook, {"opaque": [None, True, "λ"]})
    )
    first = await incoming.get()
    second = await incoming.get()
    for data in (first, second):
        assert data["message"] == {"opaque": [None, True, "λ"]}
        assert messages.report(
            notebook.id, reply(data), keys[data["attachment_id"]]
        )
    assert await task == SendResult(
        (
            RecipientResult("same", "submitted"),
            RecipientResult("other", "submitted"),
        )
    )
    assert incoming.empty()


async def test_targeting_and_report_authority(setup) -> None:
    host, notebook, messages = setup
    first = notebook.attach(kind="agent", identity="first")
    second = notebook.attach(kind="agent", identity="second")
    key = messages.register(notebook, first.id)
    other_key = messages.register(notebook, second.id)
    incoming = listen(host, notebook)
    task = asyncio.create_task(messages.send(notebook, [1, None], to="first"))
    data = await incoming.get()
    assert data["attachment_id"] == first.id
    assert not messages.report(notebook.id, reply(data), other_key)
    assert not messages.report("another-notebook", reply(data), key)
    assert not messages.report(
        notebook.id,
        SubmissionReport(second.id, data["attempt_id"], "submitted"),
        other_key,
    )
    assert not messages.report(
        notebook.id, SubmissionReport(first.id, "unrelated", "submitted"), key
    )
    assert messages.report(notebook.id, reply(data, "unknown"), key)
    assert not messages.report(notebook.id, reply(data), key)
    assert await task == SendResult((RecipientResult("first", "unknown"),))
    assert not messages.report(notebook.id, reply(data), key)
    assert incoming.empty()


async def test_missing_target_and_old_forwarder_never_dispatch(setup) -> None:
    host, notebook, messages = setup
    notebook.attach(kind="agent", identity="old")
    incoming = listen(host, notebook)
    missing = await messages.send(notebook, "message", to="absent")
    old = await messages.send(notebook, "message", to="old")
    assert (
        missing.recipients[0].status == old.recipients[0].status == "rejected"
    )
    assert incoming.empty()


async def test_empty_listing_and_broadcast(setup) -> None:
    _, notebook, messages = setup
    assert messages.list(notebook) == ()
    with pytest.raises(NoAgentsConnectedError):
        await messages.broadcast(notebook, None)


async def test_disconnect_and_reconnect_do_not_transfer_attempt(setup) -> None:
    host, notebook, messages = setup
    old = notebook.attach(kind="agent", identity="agent")
    old_key = messages.register(notebook, old.id)
    incoming = listen(host, notebook)
    task = asyncio.create_task(messages.send(notebook, "once", to="agent"))
    data = await incoming.get()
    notebook.detach(old.id)
    new = notebook.attach(kind="agent", identity="agent")
    new_key = messages.register(notebook, new.id)
    assert (await task).recipients[0].status == "unknown"
    assert not messages.report(notebook.id, reply(data), old_key)
    assert not messages.report(
        notebook.id,
        SubmissionReport(new.id, data["attempt_id"], "submitted"),
        new_key,
    )
    assert messages.list(notebook) == (AgentInfo("agent", None),)
    assert incoming.empty()


async def test_broadcast_membership_and_one_deadline(setup) -> None:
    host, notebook, messages = setup
    attachments = [
        notebook.attach(kind="agent", identity=str(i)) for i in range(3)
    ]
    keys = [messages.register(notebook, a.id) for a in attachments]
    incoming = listen(host, notebook)
    started = asyncio.get_running_loop().time()
    task = asyncio.create_task(
        messages.broadcast(notebook, None, timeout=0.05)
    )
    first = await incoming.get()
    notebook.attach(kind="agent", identity="late")
    messages.report(notebook.id, reply(first), keys[0])
    result = await task
    assert [(r.agent_id, r.status) for r in result.recipients] == [
        ("0", "submitted"),
        ("1", "unknown"),
        ("2", "unknown"),
    ]
    assert asyncio.get_running_loop().time() - started < 0.3
    assert not messages.report(notebook.id, reply(first), keys[0])


@pytest.mark.parametrize("end", ["cancel", "close", "remove"])
async def test_cleanup_releases_waiters_and_capacity(setup, end: str) -> None:
    host, notebook, _ = setup
    messages = AgentMessaging(host, capacity=1)
    attachment = notebook.attach(kind="agent", identity="agent")
    messages.register(notebook, attachment.id)
    incoming = listen(host, notebook)
    task = asyncio.create_task(messages.send(notebook, "once", to="agent"))
    await incoming.get()
    with pytest.raises(AgentError, match="Too many"):
        await messages.send(notebook, "overflow", to="agent")
    assert incoming.empty()
    if end == "cancel":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (
            await messages.send(notebook, "new", to="agent", timeout=0.001)
        ).recipients[0].status == "unknown"
    else:
        if end == "close":
            messages.close()
        else:
            host.remove_notebook(notebook.id)
        assert (await task).recipients[0].status == "unknown"
    if end == "close":
        with pytest.raises(AgentContextUnavailableError):
            messages.list(notebook)


@pytest.mark.parametrize(
    ("timeout", "error"),
    [
        (True, TypeError),
        ("1", TypeError),
        (0, ValueError),
        (-1, ValueError),
        (float("inf"), ValueError),
        (float("nan"), ValueError),
        (1e10, ValueError),
    ],
)
async def test_invalid_timeout_never_dispatches(setup, timeout, error) -> None:
    host, notebook, messages = setup
    incoming = listen(host, notebook)
    with pytest.raises(error):
        await messages.broadcast(notebook, "no", timeout=timeout)
    assert incoming.empty()


@pytest.mark.parametrize(
    ("message", "error"),
    [
        ({1: "key"}, TypeError),
        ({"set": {1}}, TypeError),
        ((1, 2), TypeError),
        (float("nan"), ValueError),
        ([float("inf")], ValueError),
    ],
)
async def test_invalid_payload_never_dispatches(setup, message, error) -> None:
    host, notebook, messages = setup
    incoming = listen(host, notebook)
    with pytest.raises(error):
        await messages.broadcast(notebook, message)
    assert incoming.empty()


async def test_cycle_rejected_but_repeated_values_allowed(setup) -> None:
    _, notebook, messages = setup
    value: list[Any] = []
    value.append(value)
    with pytest.raises(ValueError, match="cycles"):
        await messages.broadcast(notebook, value)
    value.clear()
    with pytest.raises(NoAgentsConnectedError):
        await messages.broadcast(notebook, [value, value])
