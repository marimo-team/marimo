# Copyright 2026 Marimo. All rights reserved.
"""Transient content and delivery ownership for notebook agent messages."""

from __future__ import annotations

import asyncio
import hmac
import math
import secrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import msgspec

from marimo._core import protocol
from marimo._messaging.agents import (
    MESSAGE_TYPE,
    MessageContent,
    MessageRequest,
    PointerEvent,
    RecipientResult,
    SendResult,
    SubmissionReason,
    SubmissionReport,
    SubmissionStatus,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from marimo._core.host import Host
    from marimo._core.notebook import Notebook
    from marimo._core.stream import RoutedEvent


@dataclass
class _Attempt:
    notebook_id: str
    attachment_id: str
    agent_id: str
    name: str | None
    content: MessageContent | None
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
        self._keys: dict[str, tuple[str, str]] = {}
        self._pending: dict[str, _Attempt] = {}
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

    def _recipients(
        self, notebook: Notebook, body: MessageRequest
    ) -> dict[str, protocol.Attachment | None]:
        recipients: dict[str, protocol.Attachment | None] = {
            candidate.identity or candidate.id: candidate
            for candidate in notebook.attachments
            if candidate.kind == "agent" and candidate.id in self._keys
        }
        if body.broadcast:
            return recipients
        assert body.to is not None
        return {body.to: recipients.get(body.to)}

    async def send(
        self, notebook: Notebook, body: MessageRequest
    ) -> SendResult:
        UUID(body.message_id)
        if (body.to is None) == (not body.broadcast) or body.to == "":
            raise ValueError("Select one agent or an explicit broadcast")
        if not math.isfinite(body.timeout) or body.timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        deadline = self._clock() + body.timeout
        recipients = self._recipients(notebook, body)
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
                    notebook.id,
                    attachment.id if attachment else "",
                    identity,
                    attachment.name if attachment else None,
                    content,
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
            del content
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
                    await asyncio.wait(
                        [*(a.result for a in pending), timer],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                finally:
                    timer.cancel()
                    await asyncio.gather(timer, return_exceptions=True)
                for attempt in pending:
                    self._expire(attempt)
            return SendResult(
                body.message_id,
                tuple(a.result.result() for a in attempts.values()),
            )
        finally:
            for attempt_id in attempts:
                attempt = self._pending.pop(attempt_id, None)
                if attempt is not None:
                    attempt.content = None

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

    def _observe(self, event: RoutedEvent) -> None:
        if isinstance(event.event, protocol.AttachmentRemovedEvent):
            self.unregister(event.event.data.id)

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
