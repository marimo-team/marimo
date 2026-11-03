# Copyright 2026 Marimo. All rights reserved.
"""Notebook-scoped agent routing and transient submission coordination."""

from __future__ import annotations

import asyncio
import hmac
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import msgspec

from marimo._core import protocol
from marimo._messaging.agents import (
    MESSAGE_TYPE,
    AgentContextUnavailableError,
    AgentError,
    AgentInfo,
    NoAgentsConnectedError,
    RecipientResult,
    SendResult,
    SubmissionReport,
    validate_message,
    validate_recipient,
    validate_timeout,
)

if TYPE_CHECKING:
    from marimo._core.host import Host
    from marimo._core.notebook import Notebook
    from marimo._core.stream import RoutedEvent


def agent_id(attachment: protocol.Attachment) -> str:
    identity = attachment.identity
    return identity if isinstance(identity, str) else attachment.id


def _agent_attachments(
    notebook: Notebook,
) -> dict[str, list[protocol.Attachment]]:
    recipients: dict[str, list[protocol.Attachment]] = {}
    for attachment in notebook.attachments:
        if attachment.kind == "agent":
            recipients.setdefault(agent_id(attachment), []).append(attachment)
    return recipients


def connected_agents(notebook: Notebook) -> tuple[AgentInfo, ...]:
    """Derive logical agents from the Notebook's live attachments."""
    return tuple(
        AgentInfo(id=identity, name=attachments[-1].name)
        for identity, attachments in _agent_attachments(notebook).items()
    )


@dataclass
class _Attempt:
    notebook_id: str
    attachment_id: str
    agent_id: str
    result: asyncio.Future[RecipientResult]


class AgentMessaging:
    """Route messages through live host attachments and await their reports.

    Access stays on the host event loop. Native delivery runs in forwarders.
    The live attachment collection remains the source of recipient membership.
    """

    def __init__(self, host: Host, *, capacity: int = 1024) -> None:
        self._capacity = capacity
        self._keys: dict[str, tuple[str, str]] = {}
        self._pending: dict[str, _Attempt] = {}
        self._closed = False
        self._unsubscribe = host.subscribe(self._observe)

    def register(self, notebook: Notebook, attachment_id: str) -> str:
        """Bind reporting support and a private credential to one stream."""
        self._require_open()
        key = secrets.token_urlsafe(32)
        self._keys[attachment_id] = (notebook.id, key)
        return key

    def unregister(self, attachment_id: str) -> None:
        self._keys.pop(attachment_id, None)
        for attempt in self._pending.values():
            if attempt.attachment_id == attachment_id:
                self._unknown(
                    attempt,
                    "The agent disconnected before reporting an outcome.",
                )

    def list(self, notebook: Notebook) -> tuple[AgentInfo, ...]:
        self._require_open()
        return connected_agents(notebook)

    async def send(
        self,
        notebook: Notebook,
        message: Any,
        *,
        to: str,
        timeout: float = 30.0,
    ) -> SendResult:
        validate_recipient(to)
        return await self._send(notebook, message, to=to, timeout=timeout)

    async def broadcast(
        self, notebook: Notebook, message: Any, *, timeout: float = 30.0
    ) -> SendResult:
        return await self._send(notebook, message, to=None, timeout=timeout)

    async def _send(
        self,
        notebook: Notebook,
        message: Any,
        *,
        to: str | None,
        timeout: float,
    ) -> SendResult:
        timeout = validate_timeout(timeout)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        validate_message(message)
        message = msgspec.json.decode(msgspec.json.encode(message))
        self._require_open()
        recipients = _agent_attachments(notebook)
        selected = list(recipients) if to is None else [to]
        if not selected:
            raise NoAgentsConnectedError("No agents are connected")
        if len(self._pending) + len(selected) > self._capacity:
            raise AgentError("Too many agent messages are pending")
        attempts: dict[str, _Attempt] = {}
        try:
            for identity in selected:
                # New streams replace delivery ownership for future sends only.
                attachments = recipients.get(identity, [])
                attachment = next(
                    (a for a in reversed(attachments) if a.id in self._keys),
                    None,
                )
                attempt = _Attempt(
                    notebook.id,
                    "" if attachment is None else attachment.id,
                    identity,
                    loop.create_future(),
                )
                attempt_id = secrets.token_urlsafe(24)
                attempts[attempt_id] = attempt
                self._pending[attempt_id] = attempt
                if attachment is None:
                    attempt.result.set_result(
                        RecipientResult(
                            identity,
                            "rejected",
                            "The agent is not connected."
                            if not attachments
                            else "Reconnect this agent to enable messaging results.",
                        )
                    )
            for attempt_id, attempt in attempts.items():
                if not attempt.result.done():
                    notebook.emit(
                        MESSAGE_TYPE,
                        {
                            "attempt_id": attempt_id,
                            "attachment_id": attempt.attachment_id,
                            "message": message,
                        },
                    )
            pending = [a.result for a in attempts.values()]
            await asyncio.wait(pending, timeout=max(0, deadline - loop.time()))
            for attempt in attempts.values():
                self._unknown(
                    attempt,
                    "No submission outcome arrived before the timeout.",
                )
            return SendResult(
                tuple(a.result.result() for a in attempts.values())
            )
        finally:
            for attempt_id in attempts:
                self._pending.pop(attempt_id, None)

    def report(
        self, notebook_id: str, report: SubmissionReport, key: str
    ) -> bool:
        """Accept a matching outcome once, without creating retained receipts."""
        registered = self._keys.get(report.attachment_id)
        if registered is None or registered[0] != notebook_id:
            return False
        if not hmac.compare_digest(registered[1].encode(), key.encode()):
            return False
        attempt = self._pending.get(report.attempt_id)
        if (
            attempt is None
            or attempt.notebook_id != notebook_id
            or attempt.attachment_id != report.attachment_id
            or attempt.result.done()
        ):
            return False
        attempt.result.set_result(
            RecipientResult(attempt.agent_id, report.status, report.detail)
        )
        return True

    def close(self) -> None:
        self._closed = True
        self._unsubscribe()
        self._keys.clear()
        for attempt in self._pending.values():
            self._unknown(
                attempt, "The host closed before reporting an outcome."
            )

    def _require_open(self) -> None:
        if self._closed:
            raise AgentContextUnavailableError(
                "Agent messaging is unavailable"
            )

    def _observe(self, event: RoutedEvent) -> None:
        if isinstance(event.event, protocol.AttachmentRemovedEvent):
            self.unregister(event.event.data.id)
        elif isinstance(event.event, protocol.NotebookRemovedEvent):
            for attachment_id, (notebook_id, _) in list(self._keys.items()):
                if notebook_id == event.event.data.id:
                    self.unregister(attachment_id)

    @staticmethod
    def _unknown(attempt: _Attempt, detail: str) -> None:
        if not attempt.result.done():
            attempt.result.set_result(
                RecipientResult(attempt.agent_id, "unknown", detail)
            )
