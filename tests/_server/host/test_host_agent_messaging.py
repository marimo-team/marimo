# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from marimo._messaging.agents import (
    ATTACHMENT_HEADER,
    MESSAGING_HEADER,
    REPORT_KEY_HEADER,
    MessageRequest,
    SendResult,
)
from marimo._server.host.agents import AgentMessaging
from tests._server.host.drive import (
    Response,
    finished,
    request,
    until_ready,
    wait_for,
)
from tests._server.host.test_host_api import IDENTIFIED, Harness, harness

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

__all__ = ["harness"]


class MessagingClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.waiters: list[tuple[float, asyncio.Future[None]]] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> asyncio.Future[None]:
        future = asyncio.get_running_loop().create_future()
        self.waiters.append((self.now + seconds, future))
        return future

    def advance(self, seconds: float) -> None:
        self.now += seconds
        for deadline, future in self.waiters:
            if deadline <= self.now and not future.done():
                future.set_result(None)


@dataclass
class MessagingRoutes:
    harness: Harness
    service: AgentMessaging
    clock: MessagingClock
    stream: Response

    @property
    def path(self) -> str:
        return f"/notebooks/{self.harness.notebook_id}/messages"

    @property
    def headers(self) -> dict[str, str]:
        return {
            **IDENTIFIED,
            ATTACHMENT_HEADER: self.stream.headers[ATTACHMENT_HEADER.lower()],
            REPORT_KEY_HEADER: self.stream.headers[REPORT_KEY_HEADER.lower()],
        }

    @property
    def attempt_id(self) -> str:
        return next(
            r["data"]["custom"]["data"]["attempt_id"]
            for r in self.stream.records
            if r.get("event") == "custom"
        )

    async def start(self, timeout: float = 30) -> asyncio.Task[SendResult]:
        task = asyncio.create_task(
            self.service.send(
                await self.harness.host.notebook(self.harness.notebook_id),
                MessageRequest(
                    str(uuid4()), "private", to="k1", timeout=timeout
                ),
            )
        )
        await wait_for(self.stream, lambda r: "custom" in r.names())
        return task

    async def fetch(self) -> Response:
        return await finished(
            self.harness.app,
            "POST",
            self.path + f"/{self.attempt_id}/content",
            headers=self.headers,
        )

    async def report(self) -> Response:
        import json

        return await finished(
            self.harness.app,
            "POST",
            self.path + "/report",
            headers=self.headers,
            body=json.dumps(
                {
                    "attachment_id": self.headers[ATTACHMENT_HEADER],
                    "attempt_id": self.attempt_id,
                    "status": "submitted",
                }
            ).encode(),
        )


@pytest.fixture
async def messaging(harness: Harness) -> AsyncIterator[MessagingRoutes]:
    clock = MessagingClock()
    harness.app.state.host_context.agents.close()
    service = AgentMessaging(harness.host, clock=clock, sleep=clock.sleep)
    harness.app.state.host_context.agents = service
    stream, task, disconnect = request(
        harness.app,
        "GET",
        f"/notebooks/{harness.notebook_id}/events",
        headers={**IDENTIFIED, MESSAGING_HEADER: "1"},
    )
    await wait_for(stream, until_ready)
    try:
        yield MessagingRoutes(harness, service, clock, stream)
    finally:
        disconnect()
        await task
        service.close()


@pytest.mark.parametrize(("timeout", "deadline"), [(30, 5), (2, 2)])
async def test_unfetched_attempt_expires(
    messaging: MessagingRoutes,
    timeout: float,
    deadline: float,
) -> None:
    send = await messaging.start(timeout)
    messaging.clock.advance(deadline - 0.001)
    await asyncio.sleep(0)
    assert not send.done()
    messaging.clock.advance(0.001)
    result = await asyncio.wait_for(send, 1)
    assert [(r.status, r.reason) for r in result.recipients] == [
        ("rejected", "timeout")
    ]
    response = await messaging.fetch()
    assert response.status == 409
    assert response.json()["type"] == "urn:marimo:problem:conflict"


async def test_fetched_attempt_waits_until_call_deadline(
    messaging: MessagingRoutes,
) -> None:
    send = await messaging.start()
    assert (await messaging.fetch()).json()["message"] == "private"
    messaging.clock.advance(5)
    await asyncio.sleep(0)
    assert not send.done()
    messaging.clock.advance(25)
    result = await asyncio.wait_for(send, 1)
    assert [(r.status, r.reason) for r in result.recipients] == [
        ("unknown", "timeout")
    ]
    assert (await messaging.report()).status == 409


@pytest.mark.parametrize("fetched", [False, True])
async def test_late_requests_cannot_beat_the_deadline(
    messaging: MessagingRoutes,
    fetched: bool,
) -> None:
    send = await messaging.start()
    if fetched:
        assert (await messaging.fetch()).status == 200
    messaging.clock.advance(30 if fetched else 5)
    response = await (messaging.report() if fetched else messaging.fetch())
    assert response.status == 409
    result = await send
    assert [(r.status, r.reason) for r in result.recipients] == [
        ("unknown" if fetched else "rejected", "timeout")
    ]


async def test_content_is_single_use_and_reports_are_final(
    messaging: MessagingRoutes,
) -> None:
    send = await messaging.start()
    assert (await messaging.fetch()).json()["message"] == "private"
    assert (await messaging.fetch()).status == 409
    assert (await messaging.report()).status == 204
    assert (await messaging.report()).status == 409
    assert (await messaging.fetch()).status == 409
    assert (await send).recipients[0].status == "submitted"
