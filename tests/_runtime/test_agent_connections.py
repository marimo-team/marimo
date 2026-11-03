# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from unittest.mock import Mock, call, patch

import msgspec
import pytest

import marimo as mo
from marimo._runtime.cell_lifecycle_registry import NoOwningCellError
from marimo._runtime.context import get_context
from marimo._types.ids import CellId_t


@pytest.fixture
def observer(k, http_endpoint):
    from marimo._messaging.agents import AgentConnection

    k.agent_messaging = AgentConnection(http_endpoint.url, "auth", "skew")
    http_endpoint.body = b"{}"
    return k, get_context(), http_endpoint


def registered_function(context):
    functions = [
        function
        for name, namespace in context.function_registry.namespaces.items()
        if name.startswith("marimo.agents.connections.")
        for function in namespace.functions.values()
    ]
    assert len(functions) == 1
    return functions[0]


def test_subscription_is_deferred_typed_and_idempotent(observer) -> None:
    _, context, endpoint = observer
    callback = Mock()
    with context.with_cell_id(CellId_t("owner")):
        unsubscribe = mo.agents.subscribe_connections(callback)
    callback.assert_not_called()
    function = registered_function(context)
    assert function.cell_id == "owner"
    function({"revision": 1, "agents": []})
    function({"revision": 2, "agents": [{"id": "a", "name": None}]})
    function({"revision": 1, "agents": []})
    function({"revision": 3, "agents": [{"id": "a", "name": None}]})
    assert callback.call_args_list == [
        call(()),
        call((mo.agents.AgentInfo("a", None),)),
    ]
    unsubscribe()
    unsubscribe()
    function({"revision": 4, "agents": []})
    assert callback.call_count == 2
    assert not context.function_registry.namespaces
    bodies = [
        msgspec.json.decode(request.body) for request in endpoint.requests
    ]
    assert len(bodies) == 2
    assert bodies[0]["active"] is True
    assert bodies[1] == {**bodies[0], "active": False}


@pytest.mark.parametrize("deletion", [False, True])
def test_cell_lifecycle_disposes_queued_callback(observer, deletion) -> None:
    _, context, _ = observer
    callback = Mock()
    cell_id = CellId_t("owner")
    with context.with_cell_id(cell_id):
        mo.agents.subscribe_connections(callback)
    function = registered_function(context)
    context.cell_lifecycle_registry.dispose(cell_id, deletion=deletion)
    function({"revision": 1, "agents": []})
    callback.assert_not_called()
    assert cell_id not in context.cell_lifecycle_registry.registry
    assert not context.function_registry.namespaces


def test_owner_is_required_before_http_registration(observer) -> None:
    _, context, endpoint = observer
    with pytest.raises(NoOwningCellError):
        mo.agents.subscribe_connections(lambda _: None)
    assert not endpoint.requests
    assert not context.function_registry.namespaces


def test_setup_failure_removes_function_and_lifecycle_item(observer) -> None:
    _, context, endpoint = observer
    endpoint.status = 503
    endpoint.body = b'{"code":"failed","detail":"Unavailable"}'
    with context.with_cell_id(CellId_t("owner")):
        with pytest.raises(mo.agents.AgentError):
            mo.agents.subscribe_connections(lambda _: None)
    assert not context.cell_lifecycle_registry.registry
    assert not context.function_registry.namespaces


def test_callback_can_unsubscribe_itself(observer) -> None:
    _, context, _ = observer
    callback = Mock(side_effect=lambda _: unsubscribe())
    with context.with_cell_id(CellId_t("owner")):
        unsubscribe = mo.agents.subscribe_connections(callback)
    function = registered_function(context)
    function({"revision": 1, "agents": []})
    function({"revision": 2, "agents": [{"id": "a", "name": None}]})
    assert callback.call_count == 1


def test_callback_errors_do_not_disable_observer(observer) -> None:
    _, context, _ = observer
    callback = Mock(side_effect=[ValueError("consumer failed"), None])
    with context.with_cell_id(CellId_t("owner")):
        unsubscribe = mo.agents.subscribe_connections(callback)
    function = registered_function(context)
    with pytest.raises(ValueError, match="consumer failed"):
        function({"revision": 1, "agents": []})
    function({"revision": 2, "agents": [{"id": "a", "name": None}]})
    assert callback.call_count == 2
    unsubscribe()


async def async_callback(_):
    await asyncio.sleep(0)


class AsyncCallable:
    async def __call__(self, _):
        pass


@pytest.mark.parametrize(
    "callback", [None, 42, async_callback, AsyncCallable()]
)
def test_invalid_callbacks_fail_before_context_resolution(callback) -> None:
    with pytest.raises(TypeError, match="synchronous"):
        mo.agents.subscribe_connections(callback)


def test_unbound_context_is_unavailable() -> None:
    with pytest.raises(mo.agents.AgentContextUnavailableError):
        mo.agents.subscribe_connections(lambda _: None)


@pytest.mark.parametrize("callback", [lambda: None, lambda _a, _b: None])
def test_callback_requires_one_snapshot_argument(callback) -> None:
    with pytest.raises(TypeError):
        mo.agents.subscribe_connections(callback)


@pytest.mark.usefixtures("run_mode_kernel")
def test_read_mode_creates_no_observer() -> None:
    with pytest.raises(mo.agents.AgentContextUnavailableError):
        mo.agents.subscribe_connections(lambda _: None)


def test_background_registration_creates_no_observer(observer) -> None:
    _, context, endpoint = observer
    with (
        context.with_cell_id(CellId_t("owner")),
        patch("marimo._runtime.threads.is_marimo_thread", return_value=True),
        pytest.raises(mo.agents.AgentContextUnavailableError),
    ):
        mo.agents.subscribe_connections(lambda _: None)
    assert not endpoint.requests
    assert not context.function_registry.namespaces
