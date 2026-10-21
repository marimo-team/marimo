# Copyright 2026 Marimo. All rights reserved.
"""Send JSON content to agents connected to this live editor Notebook.

Each call is a new send, including calls on reactive reruns. Prefer explicit
callbacks for user actions. Submission does not mean reading or task completion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import msgspec

from marimo._messaging.agents import (
    AgentInfo,
    AgentMessagingError,
    MessagingUnavailableError,
    NoAgentsConnectedError,
    RecipientResult,
    SendOutcomeUnknownError,
    SendResult,
    validate_message,
    validate_recipient,
    validate_timeout,
)

if TYPE_CHECKING:
    from marimo._messaging.agents import AgentConnection

__all__ = [
    "AgentInfo",
    "AgentMessagingError",
    "MessagingUnavailableError",
    "NoAgentsConnectedError",
    "RecipientResult",
    "SendOutcomeUnknownError",
    "SendResult",
    "broadcast",
    "list",
    "send",
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
        raise MessagingUnavailableError(
            "Agent messaging requires a live editor Notebook"
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
        raise AgentMessagingError(
            "The agent listing response is invalid"
        ) from error


def _send_result(value: Any) -> SendResult:
    try:
        return msgspec.convert(value, type=SendResult)
    except msgspec.ValidationError as error:
        raise SendOutcomeUnknownError(
            "The submission response is invalid. Another send can duplicate the message."
        ) from error


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
