# Copyright 2026 Marimo. All rights reserved.
"""Transient content and delivery ownership for notebook agent messages."""

from __future__ import annotations

import asyncio
import hmac
import math
import secrets
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import msgspec

from marimo._core import protocol
from marimo._messaging.agents import (
    MESSAGE_TYPE,
    AgentInfo,
    MessageContent,
    MessageRequest,
    PointerEvent,
    RecipientResult,
    SendResult,
    SubmissionReason,
    SubmissionReport,
    SubmissionStatus,
    validate_message_size,
    validate_sender,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from marimo._core.host import Host
    from marimo._core.notebook import Notebook
    from marimo._core.stream import RoutedEvent


@dataclass
class _Attempt:
    message_id: UUID
    notebook_id: str
    attachment_id: str
    agent_id: str
    name: str | None
    content: MessageContent | None
    content_bytes: int
    result: asyncio.Future[RecipientResult]
    fetch_deadline: float
    deadline: float


class AgentMessaging:
    """Keep content off the shared stream and bind each fetch to one attachment."""

    def __init__(
        self,
        host: Host,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._sleep: Callable[[float], Awaitable[None]] = sleep
        self._clock = clock
        self._host = host
        self._first_connection: dict[str, dict[str, float]] = {}
        self._keys: dict[str, tuple[str, str]] = {}
        self._pending: dict[str, _Attempt] = {}
        self._recent: dict[str, deque[UUID]] = {}
        self._unsubscribe = host.subscribe(self._observe)

    def register(self, notebook: Notebook, attachment_id: str) -> str:
        key = secrets.token_urlsafe(32)
        self._keys[attachment_id] = (notebook.id, key)
        return key

    def unregister(self, attachment_id: str) -> None:
        self._keys.pop(attachment_id, None)
        for attempt in self._pending.values():
            if attempt.attachment_id == attachment_id:
                self._expire(attempt)
                self._finish(attempt, "disconnected")

    def _capable_attachments(
        self, notebook: Notebook
    ) -> dict[str, protocol.Attachment]:
        return {
            candidate.identity or candidate.id: candidate
            for candidate in notebook.attachments
            if candidate.kind == "agent" and candidate.id in self._keys
        }

    def list(self, notebook: Notebook) -> tuple[AgentInfo, ...]:
        """Return capable agents in stable first connection order."""
        recipients = self._capable_attachments(notebook)
        first = self._first_connection.get(notebook.id, {})
        return tuple(
            AgentInfo(identity, attachment.name or identity)
            for identity, attachment in sorted(
                recipients.items(), key=lambda item: (first[item[0]], item[0])
            )
        )

    async def send(
        self, notebook: Notebook, body: MessageRequest
    ) -> SendResult:
        message_id_text = body.message_id
        message_id = UUID(message_id_text)
        if (body.to is None) == (not body.broadcast) or body.to == "":
            raise ValueError("Select one agent or an explicit broadcast")
        if not math.isfinite(body.timeout) or body.timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        validate_sender(body.sender)
        deadline = self._clock() + body.timeout
        capable = self._capable_attachments(notebook)
        recipients: dict[str, protocol.Attachment | None] = dict(capable)
        if not body.broadcast:
            assert body.to is not None
            recipients = {body.to: capable.get(body.to)}
        recent = self._recent.setdefault(notebook.id, deque(maxlen=1024))
        if message_id in recent or any(
            a.notebook_id == notebook.id and a.message_id == message_id
            for a in self._pending.values()
        ):
            raise ValueError("Message ID is already held")
        content_bytes = validate_message_size(body.message)
        pending = [
            a
            for a in self._pending.values()
            if a.notebook_id == notebook.id and not a.result.done()
        ]
        if (
            len(pending) + sum(a is not None for a in recipients.values())
            > 1024
        ):
            raise ValueError("Notebook exceeds 1024 pending attempts")
        retained = {
            id(a.content): a.content_bytes
            for a in pending
            if a.content is not None
        }
        if (
            sum(retained.values())
            + (content_bytes if any(recipients.values()) else 0)
            > 64 * 1024 * 1024
        ):
            raise ValueError("Notebook exceeds 64 MB of pending content")
        recent.append(message_id)
        content = MessageContent(
            body.message,
            self._host.notebooks[notebook.id].path or notebook.id,
            body.sender,
        )
        attempts: dict[str, _Attempt] = {}
        loop = asyncio.get_running_loop()
        try:
            for identity, attachment in recipients.items():
                attempt = _Attempt(
                    message_id,
                    notebook.id,
                    attachment.id if attachment else "",
                    identity,
                    attachment.name if attachment else None,
                    content,
                    content_bytes,
                    loop.create_future(),
                    min(deadline, self._clock() + 5.0),
                    deadline,
                )
                attempt_id = secrets.token_urlsafe(24)
                attempts[attempt_id] = attempt
                self._pending[attempt_id] = attempt
                if attachment is None:
                    self._finish(attempt, "not-connected")
                else:
                    notebook.emit(
                        MESSAGE_TYPE,
                        msgspec.to_builtins(
                            PointerEvent(
                                body.message_id,
                                attempt_id,
                                attachment.id,
                                identity,
                                body.sender,
                            )
                        ),
                    )
            del content, body
            while pending := [
                a for a in attempts.values() if not a.result.done()
            ]:
                next_deadline = min(
                    a.fetch_deadline if a.content is not None else a.deadline
                    for a in pending
                )
                timer = asyncio.ensure_future(
                    self._sleep(max(0, next_deadline - self._clock()))
                )
                try:
                    waiters: list[
                        asyncio.Future[RecipientResult] | asyncio.Future[None]
                    ] = [*(a.result for a in pending), timer]
                    await asyncio.wait(
                        waiters,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                finally:
                    timer.cancel()
                    await asyncio.gather(timer, return_exceptions=True)
                for attempt in pending:
                    self._expire(attempt)
            return SendResult(
                message_id_text,
                tuple(a.result.result() for a in attempts.values()),
            )
        finally:
            for attempt_id in attempts:
                removed = self._pending.pop(attempt_id, None)
                if removed is not None:
                    removed.content = None

    def _authorize(
        self, notebook_id: str, attachment_id: str, key: str
    ) -> None:
        registered = self._keys.get(attachment_id)
        if (
            registered is None
            or registered[0] != notebook_id
            or not hmac.compare_digest(registered[1].encode(), key.encode())
        ):
            raise PermissionError("Invalid report key")

    def _attempt(
        self, notebook_id: str, attachment_id: str, attempt_id: str, key: str
    ) -> _Attempt:
        self._authorize(notebook_id, attachment_id, key)
        attempt = self._pending.get(attempt_id)
        if attempt is not None:
            self._expire(attempt)
        if (
            attempt is None
            or attempt.notebook_id != notebook_id
            or attempt.attachment_id != attachment_id
            or attempt.result.done()
        ):
            raise ValueError("Attempt is no longer pending")
        return attempt

    def fetch(
        self, notebook_id: str, attachment_id: str, attempt_id: str, key: str
    ) -> MessageContent:
        attempt = self._attempt(notebook_id, attachment_id, attempt_id, key)
        content = attempt.content
        if content is None:
            raise ValueError("Content was already fetched")
        attempt.content = None
        return content

    def report(
        self, notebook_id: str, report: SubmissionReport, key: str
    ) -> None:
        attempt = self._attempt(
            notebook_id, report.attachment_id, report.attempt_id, key
        )
        if attempt.content is not None:
            raise ValueError("Fetch content before reporting")
        if report.status == "submitted" and report.reason is not None:
            raise ValueError("Submitted has no reason")
        if report.status != "submitted" and report.reason is None:
            raise ValueError("An unsuccessful submission needs a reason")
        attempt.result.set_result(
            RecipientResult(
                attempt.agent_id,
                attempt.name,
                report.status,
                report.reason,
                report.detail[:500] if report.detail else None,
            )
        )

    def close(self) -> None:
        self._unsubscribe()
        for attachment_id in list(self._keys):
            self.unregister(attachment_id)
        self._recent.clear()
        self._first_connection.clear()

    def _observe(self, event: RoutedEvent) -> None:
        if isinstance(event.event, protocol.AttachmentEvent):
            attachment = event.event.data.attachment
            if attachment.kind == "agent":
                self._first_connection.setdefault(
                    attachment.notebook_id, {}
                ).setdefault(
                    attachment.identity or attachment.id, self._clock()
                )
        elif isinstance(event.event, protocol.AttachmentRemovedEvent):
            self.unregister(event.event.data.id)
        elif isinstance(event.event, protocol.NotebookRemovedEvent):
            self._recent.pop(event.event.data.id, None)
            self._first_connection.pop(event.event.data.id, None)

    def _expire(self, attempt: _Attempt) -> None:
        deadline = (
            attempt.fetch_deadline
            if attempt.content is not None
            else attempt.deadline
        )
        if self._clock() >= deadline:
            self._finish(attempt, "timeout")

    @staticmethod
    def _finish(attempt: _Attempt, reason: SubmissionReason) -> None:
        if not attempt.result.done():
            status: SubmissionStatus = (
                "rejected" if attempt.content is not None else "unknown"
            )
            attempt.content = None
            attempt.result.set_result(
                RecipientResult(attempt.agent_id, attempt.name, status, reason)
            )
