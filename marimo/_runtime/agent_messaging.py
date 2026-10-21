# Copyright 2026 Marimo. All rights reserved.
"""Synchronous Python client of the editor's agent messaging endpoints."""

from __future__ import annotations

from time import monotonic
from typing import Any, Literal
from urllib.parse import urlsplit

import msgspec

from marimo._messaging.agents import (
    AgentConnection,
    AgentMessagingError,
    MessageError,
    MessageRequest,
    MessagingUnavailableError,
    NoAgentsConnectedError,
    SendOutcomeUnknownError,
)
from marimo._utils.requests import RequestError, request

_MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def _lost(operation: str) -> AgentMessagingError:
    if operation == "list":
        return AgentMessagingError(
            "The agent listing response was lost or timed out"
        )
    return SendOutcomeUnknownError(
        "The submission outcome is unknown. Another send can duplicate the message."
    )


def _http_error(
    status: int, data: bytes, operation: str
) -> AgentMessagingError:
    if status in {401, 403, 404, 405}:
        return MessagingUnavailableError(
            "The editor agent messaging endpoint is unavailable or unauthorized"
        )
    if status in {400, 409, 503}:
        try:
            error = msgspec.json.decode(data, type=MessageError)
        except msgspec.DecodeError:
            return _lost(operation)
        match error.code:
            case "unavailable":
                return MessagingUnavailableError(error.detail)
            case "no-agents":
                return NoAgentsConnectedError(error.detail)
            case "invalid-argument" | "failed":
                return AgentMessagingError(error.detail)
    return _lost(operation)


def call(
    config: AgentConnection,
    operation: Literal["list", "send", "broadcast"],
    *,
    timeout: float,
    message: Any = None,
    to: str | None = None,
) -> Any:
    """Call the same authenticated endpoints used by browser controls."""
    deadline = monotonic() + timeout

    endpoint = urlsplit(config.url)
    if (
        endpoint.scheme not in {"http", "https"}
        or endpoint.hostname is None
        or endpoint.username is not None
        or endpoint.password is not None
        or endpoint.query
        or endpoint.fragment
    ):
        raise MessagingUnavailableError("Invalid agent messaging endpoint")
    headers = {
        "Content-Type": "application/json",
        "Marimo-Server-Token": config.server_token,
    }
    if config.auth_token:
        headers["Authorization"] = f"Bearer {config.auth_token}"
    body = (
        None
        if operation == "list"
        else msgspec.json.encode(
            MessageRequest(
                message,
                to=to,
                broadcast=operation == "broadcast",
                timeout=max(0, deadline - monotonic()),
            )
        )
    )
    url = config.url.rstrip("/") + (
        "/agents" if operation == "list" else "/messages"
    )
    try:
        response = request(
            "GET" if operation == "list" else "POST",
            url,
            data=body,
            headers=headers,
            deadline=deadline,
            max_response_bytes=_MAX_RESPONSE_BYTES,
        )
    except RequestError as error:
        if error.status_code in {401, 403, 404, 405}:
            raise _http_error(error.status_code, b"", operation) from error
        if error.dispatched is False:
            raise MessagingUnavailableError(
                "Could not connect to the editor agent messaging endpoint"
            ) from error
        raise _lost(operation) from error
    if response.status_code != 200:
        raise _http_error(response.status_code, response.content, operation)
    if monotonic() >= deadline:
        raise _lost(operation)
    try:
        return msgspec.json.decode(response.content)
    except msgspec.DecodeError as error:
        raise _lost(operation) from error
