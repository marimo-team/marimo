# Copyright 2026 Marimo. All rights reserved.
"""Send JSON content to agents connected to this live editor Notebook.

Each call is a new send, including calls on reactive reruns. Prefer explicit
callbacks for user actions. Submission does not mean reading or task completion.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Literal

import msgspec

from marimo._messaging.agents import (
    AgentContextUnavailableError,
    AgentError,
    AgentInfo,
    NoAgentsConnectedError,
    RecipientResult,
    SendOutcomeUnknownError,
    SendResult,
    validate_message,
    validate_recipient,
    validate_timeout,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._messaging.agents import AgentConnection

__all__ = [
    "AgentContextUnavailableError",
    "AgentError",
    "AgentInfo",
    "NoAgentsConnectedError",
    "RecipientResult",
    "SendOutcomeUnknownError",
    "SendResult",
    "broadcast",
    "list",
    "send",
    "subscribe_connections",
]


def _connection() -> AgentConnection:
    from marimo._runtime.context import safe_get_context
    from marimo._runtime.context.kernel_context import KernelRuntimeContext
    from marimo._session.model import SessionMode
    from marimo._utils.platform import is_pyodide

    ctx = safe_get_context()
    while ctx is not None and ctx.parent is not None:
        ctx = ctx.parent
    if (
        is_pyodide()
        or not isinstance(ctx, KernelRuntimeContext)
        or ctx.session_mode is not SessionMode.EDIT
        or ctx._kernel.agent_messaging is None
    ):
        raise AgentContextUnavailableError(
            "Agent operations require a live editor Notebook"
        )
    return ctx._kernel.agent_messaging


def _call(
    operation: Literal["list", "send", "broadcast"],
    *,
    timeout: float,
    message: Any = None,
    to: str | None = None,
) -> Any:
    config = _connection()
    from marimo._runtime.agent_messaging import call

    return call(config, operation, timeout=timeout, message=message, to=to)


def list(*, timeout: float = 30.0) -> tuple[AgentInfo, ...]:  # noqa: A001
    """List connected agents. Names are optional and are not unique.

    Args:
        timeout (float, optional): Maximum wait in seconds. Defaults to 30.

    Returns:
        An immutable tuple of logical agent connections in this Notebook.
    """
    timeout = validate_timeout(timeout)
    try:
        return msgspec.convert(
            _call("list", timeout=timeout),
            type=tuple[AgentInfo, ...],
        )
    except msgspec.ValidationError as error:
        raise AgentError("The agent listing response is invalid") from error


def _send_result(value: Any) -> SendResult:
    try:
        return msgspec.convert(value, type=SendResult)
    except msgspec.ValidationError as error:
        raise SendOutcomeUnknownError(
            "The submission response is invalid. Another send can duplicate the message."
        ) from error


def subscribe_connections(
    callback: Callable[[tuple[AgentInfo, ...]], None],
) -> Callable[[], None]:
    """Observe connected agents in the current live editor Notebook.

    Args:
        callback (Callable): Synchronous function that receives an immutable
            tuple of `AgentInfo` values. An empty tuple means no agents.

    Returns:
        An idempotent function that removes this subscription.

    The first callback runs after this function returns. Callbacks use normal
    kernel dispatch and wait while the kernel is busy. Pending changes can
    coalesce into the latest state. Updates do not rerun notebook cells.
    Cell reruns, deletion, and runtime shutdown remove the subscription.
    Register from a cell or synchronous widget callback. Background thread
    registration, including `mo.Thread`, is unsupported.

    Raises:
        TypeError: The callback is not callable or is asynchronous.
        AgentContextUnavailableError: No live editor runtime is available.
        NoOwningCellError: No cell can own this subscription.
    """
    if not callable(callback) or any(
        check(value)
        for check in (inspect.iscoroutinefunction, inspect.isasyncgenfunction)
        for value in (
            callback,
            getattr(callback, "__call__", None),  # noqa: B004
        )
    ):
        raise TypeError("Agent connection callbacks must be synchronous")
    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        pass
    else:
        signature.bind(())
    config = _connection()
    from marimo._runtime.agent_connections import ConnectionSubscription
    from marimo._runtime.context import get_context
    from marimo._runtime.threads import is_marimo_thread

    if is_marimo_thread():
        raise AgentContextUnavailableError(
            "Register agent connection callbacks from a notebook cell or widget callback"
        )
    subscription = ConnectionSubscription(config, callback)
    get_context().cell_lifecycle_registry.add(subscription)
    return subscription.close


def send(message: Any, *, to: str, timeout: float = 30.0) -> SendResult:
    """Send JSON content to one explicit agent and await its submission result.

    Args:
        message (Any): A JSON value. Objects require string keys.
        to (str): The opaque ID returned by `mo.agents.list()`.
        timeout (float, optional): Maximum wait in seconds. Defaults to 30.

    Returns:
        The selected agent's submission result. An absent target is rejected.

    A timeout stops the wait. It does not cancel delivery. An unknown outcome
    means that another explicit send can duplicate the content.
    """
    timeout = validate_timeout(timeout)
    validate_recipient(to)
    validate_message(message)
    return _send_result(
        _call("send", message=message, to=to, timeout=timeout),
    )


def broadcast(message: Any, *, timeout: float = 30.0) -> SendResult:
    """Send JSON content to a snapshot of all connected agents.

    Args:
        message (Any): A JSON value. Objects require string keys.
        timeout (float, optional): One wait budget for all agents, in seconds.

    Returns:
        One submission result per selected logical agent.

    Raises:
        NoAgentsConnectedError: No agents are connected at acceptance.
    """
    timeout = validate_timeout(timeout)
    validate_message(message)
    return _send_result(
        _call("broadcast", message=message, timeout=timeout),
    )
