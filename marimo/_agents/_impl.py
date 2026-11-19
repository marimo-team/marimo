# Copyright 2026 Marimo. All rights reserved.
"""Agent operations for notebook cells and widget callbacks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import msgspec

from marimo._agents._futures import SendFuture, send_queue
from marimo._messaging.agents import (
    AgentContextUnavailableError,
    AgentError,
    AgentInfo,
    SendOutcomeUnknownError,
    SendResult,
    validate_message,
    validate_message_size,
    validate_recipient,
    validate_sender,
    validate_timeout,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._messaging.agents import AgentConnection


def _connection() -> AgentConnection:
    from marimo._runtime.context import safe_get_context
    from marimo._runtime.context.kernel_context import KernelRuntimeContext

    ctx = safe_get_context()
    if ctx is None:
        raise AgentContextUnavailableError("No marimo context on this thread")
    while ctx.parent is not None:
        ctx = ctx.parent
    if (
        not isinstance(ctx, KernelRuntimeContext)
        or ctx._kernel.agent_messaging is None
    ):
        raise AgentError("Agent messaging requires a live editor notebook")
    return ctx._kernel.agent_messaging


def available() -> bool:
    """Return whether this process supports messaging, without a request.

    Connected agents are not required.

    Examples:
        ```python
        import marimo as mo

        mo.agents.available()
        ```
    """
    try:
        _connection()
    except AgentError:
        return False
    return True


def list(*, timeout: float = 30.0) -> tuple[AgentInfo, ...]:  # noqa: A001
    """List agents that can receive, in first connection order.

    Args:
        timeout (float, optional): Maximum wait in seconds. Defaults to 30.

    Examples:
        ```python
        import marimo as mo

        agents = mo.agents.list()
        [(agent.id, agent.name) for agent in agents]
        ```
    """
    from marimo._runtime.agent_messaging import call

    timeout = validate_timeout(timeout)
    try:
        return msgspec.convert(
            call(_connection(), "list", timeout=timeout),
            type=tuple[AgentInfo, ...],
        )
    except msgspec.ValidationError as error:
        raise AgentError("The agent listing response is invalid") from error


def _validate_send(message: Any, sender: str | None, timeout: float) -> float:
    timeout = validate_timeout(timeout)
    validate_message(message)
    validate_sender(sender)
    validate_message_size(message)
    return timeout


def _send(
    message: Any,
    to: str | None,
    sender: str | None,
    timeout: float,
    message_id: str,
    config: AgentConnection,
) -> SendResult:
    from marimo._runtime.agent_messaging import call

    value = call(
        config,
        "broadcast" if to is None else "send",
        message=message,
        to=to,
        sender=sender,
        message_id=message_id,
        timeout=timeout,
    )
    try:
        return msgspec.convert(value, type=SendResult)
    except msgspec.ValidationError as error:
        raise SendOutcomeUnknownError(
            "The submission response is invalid. Another send can duplicate the message."
        ) from error


def send(
    message: Any, *, to: str, sender: str | None = None, timeout: float = 30.0
) -> SendResult:
    """Send JSON data to one agent and wait for its submission result.

    Args:
        message (Any): JSON content. Objects require string keys.
        to (str): Recipient ID from `mo.agents.list()`.
        sender (str, optional): Unverified label, at most 64 characters, one line.
        timeout (float, optional): Total wait in seconds. Defaults to 30.

    Each call creates a Message ID. A reactive rerun sends again. An unknown
    outcome means another send can duplicate the message. Submission does not
    mean the model read the message or completed a task.

    Examples:
        ```python
        import marimo as mo

        agents = mo.agents.list()
        if len(agents) == 1:
            result = mo.agents.send({"rows": [1, 3]}, to=agents[0].id)
            print(result.recipients)
        ```
    """
    validate_recipient(to)
    timeout = _validate_send(message, sender, timeout)
    return _send(message, to, sender, timeout, str(uuid4()), _connection())


def broadcast(
    message: Any, *, sender: str | None = None, timeout: float = 30.0
) -> SendResult:
    """Send JSON data to all agents that can receive.

    Args:
        message (Any): JSON content. Objects require string keys.
        sender (str, optional): Unverified label, at most 64 characters, one line.
        timeout (float, optional): Total wait in seconds. Defaults to 30.

    An empty broadcast returns a result with no recipients.

    Examples:
        ```python
        import marimo as mo

        result = mo.agents.broadcast({"note": "The data changed."})
        print(result.recipients)
        ```
    """
    timeout = _validate_send(message, sender, timeout)
    return _send(message, None, sender, timeout, str(uuid4()), _connection())


def _start_send(
    message: Any, to: str | None, sender: str | None, timeout: float
) -> SendFuture:
    timeout = _validate_send(message, sender, timeout)
    config = _connection()
    # The producer can change its content after this call returns.
    message = msgspec.json.decode(msgspec.json.encode(message))
    future = SendFuture(str(uuid4()))
    send_queue.submit(
        future,
        lambda: _send(message, to, sender, timeout, future.message_id, config),
    )
    return future


def start_send(
    message: Any, *, to: str, sender: str | None = None, timeout: float = 30.0
) -> SendFuture:
    """Queue a send to one agent and return a standard future immediately.

    Args:
        message (Any): JSON content. Objects require string keys.
        to (str): Recipient ID from `mo.agents.list()`.
        sender (str, optional): Unverified label, at most 64 characters, one line.
        timeout (float, optional): Send wait in seconds after dispatch. Defaults to 30.

    The future's `message_id` is available at once. Done callbacks run on a
    marimo thread. A callback added after completion runs on the caller's thread,
    as with any standard future. Arguments and context are checked at the call;
    request errors appear in the future. At most four sends run at once.
    Each reactive rerun sends again. Submission does not mean task completion.

    Examples:
        ```python
        import marimo as mo

        agents = mo.agents.list()
        if len(agents) == 1:
            future = mo.agents.start_send({"rows": [1, 3]}, to=agents[0].id)
            print(future.message_id)
        ```
    """
    validate_recipient(to)
    return _start_send(message, to, sender, timeout)


def start_broadcast(
    message: Any, *, sender: str | None = None, timeout: float = 30.0
) -> SendFuture:
    """Queue a broadcast and return a standard future immediately.

    Args:
        message (Any): JSON content. Objects require string keys.
        sender (str, optional): Unverified label, at most 64 characters, one line.
        timeout (float, optional): Send wait in seconds after dispatch. Defaults to 30.

    The future exposes `message_id` before completion and has the same callback
    and error behavior as `start_send`. An empty broadcast has no recipients.

    Examples:
        ```python
        import marimo as mo

        future = mo.agents.start_broadcast({"note": "The data changed."})
        print(future.message_id)
        ```
    """
    return _start_send(message, None, sender, timeout)


def subscribe_connections(
    callback: Callable[[tuple[AgentInfo, ...]], None],
) -> Callable[[], None]:
    """Run a callback as agents connect or disconnect.

    Args:
        callback (Callable): Synchronous function that receives an immutable
            tuple of `AgentInfo` values. An empty tuple means no agents.

    Returns:
        A function that removes this subscription. Repeated calls are safe.

    Callbacks run on the kernel queue without an owning cell. A busy kernel
    delays callbacks, and intermediate changes can be skipped. Callbacks do not
    rerun cells. Capture the objects that your callback needs in a closure.

    Call the returned function to unsubscribe. Cell reruns
    and deletion do not remove subscriptions. Session shutdown removes them.
    Registration waits at most one second for the editor response.
    Background thread registration is unsupported.

    Raises:
        TypeError: The callback is not callable or returns an awaitable.
        AgentError: The editor does not answer or rejects registration.

    Examples:
        ```python
        import marimo as mo


        def show_connections(agents):
            print([(agent.id, agent.name) for agent in agents])


        unsubscribe = mo.agents.subscribe_connections(show_connections)
        ```

        To remove the subscription, run `unsubscribe()`.
    """
    if not callable(callback):
        raise TypeError("Agent connection callback must be callable")
    config = _connection()
    from marimo._runtime.agent_connections import ConnectionSubscription
    from marimo._runtime.context import get_context
    from marimo._runtime.threads import is_marimo_thread

    if is_marimo_thread():
        raise AgentContextUnavailableError(
            "Register agent connection callbacks from a notebook cell or widget callback"
        )
    subscription = ConnectionSubscription(config, callback)
    subscription.create(get_context().function_registry)
    return subscription.close
