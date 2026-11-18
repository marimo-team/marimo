# Copyright 2026 Marimo. All rights reserved.
"""Blocking agent operations for notebook cells and widget callbacks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import msgspec

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


def _send(
    message: Any, to: str | None, sender: str | None, timeout: float
) -> SendResult:
    from marimo._runtime.agent_messaging import call

    timeout = validate_timeout(timeout)
    validate_message(message)
    validate_sender(sender)
    validate_message_size(message)
    value = call(
        _connection(),
        "broadcast" if to is None else "send",
        message=message,
        to=to,
        sender=sender,
        message_id=str(uuid4()),
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
    """
    validate_recipient(to)
    return _send(message, to, sender, timeout)


def broadcast(
    message: Any, *, sender: str | None = None, timeout: float = 30.0
) -> SendResult:
    """Send JSON data to all agents that can receive.

    Args:
        message (Any): JSON content. Objects require string keys.
        sender (str, optional): Unverified label, at most 64 characters, one line.
        timeout (float, optional): Total wait in seconds. Defaults to 30.

    An empty broadcast returns a result with no recipients.
    """
    return _send(message, None, sender, timeout)
