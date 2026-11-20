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
            for r in reversed(self.stream.records)
            if r.get("event") == "custom"
        )

    async def start(
        self,
        timeout: float = 30,
        *,
        message: str = "private",
        broadcast: bool = False,
    ) -> asyncio.Task[SendResult]:
        count = self.stream.names().count("custom")
        task = asyncio.create_task(
            self.service.send(
                await self.harness.host.notebook(self.harness.notebook_id),
                MessageRequest(
                    str(uuid4()),
                    message,
                    to=None if broadcast else "k1",
                    broadcast=broadcast,
                    timeout=timeout,
                ),
            )
        )
        await wait_for(
            self.stream, lambda r: r.names().count("custom") > count
        )
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


async def test_attempt_limit_refuses_the_whole_broadcast(
    messaging: MessagingRoutes,
) -> None:
    notebook = await messaging.harness.host.notebook(
        messaging.harness.notebook_id
    )
    second, stream_task, disconnect = request(
        messaging.harness.app,
        "GET",
        f"/notebooks/{notebook.id}/events",
        headers={
            **IDENTIFIED,
            "Marimo-Attachment-Identity": "k2",
            MESSAGING_HEADER: "1",
        },
    )
    await wait_for(second, until_ready)
    sends = []
    try:
        for _ in range(1023):
            sends.append(await messaging.start())
            await asyncio.sleep(0)
        before = len(messaging.stream.records)
        with pytest.raises(ValueError, match="1024"):
            await asyncio.wait_for(
                messaging.service.send(
                    notebook,
                    MessageRequest(str(uuid4()), "overflow", broadcast=True),
                ),
                1,
            )
        await asyncio.sleep(0)
        assert len(messaging.stream.records) == before
        sends.append(await messaging.start())
        with pytest.raises(ValueError, match="1024"):
            await asyncio.wait_for(
                messaging.service.send(
                    notebook, MessageRequest(str(uuid4()), "overflow", to="k1")
                ),
                1,
            )
        messaging.clock.advance(5)
        await asyncio.gather(*sends)
        send = await messaging.start()
        assert (await messaging.fetch()).status == 200
        assert (await messaging.report()).status == 204
        assert (await send).recipients[0].status == "submitted"
    finally:
        for send in sends:
            send.cancel()
        await asyncio.gather(*sends, return_exceptions=True)
        disconnect()
        await stream_task


async def test_content_limit_counts_a_broadcast_once_and_releases_after_fetch(
    messaging: MessagingRoutes,
) -> None:
    h = messaging.harness
    second, stream_task, disconnect = request(
        h.app,
        "GET",
        f"/notebooks/{h.notebook_id}/events",
        headers={
            **IDENTIFIED,
            "Marimo-Attachment-Identity": "k2",
            MESSAGING_HEADER: "1",
        },
    )
    await wait_for(second, until_ready)
    sends = []
    notebook = await h.host.notebook(h.notebook_id)
    message = "x" * (4 * 1024 * 1024 - 2)
    overflow_id = str(uuid4())

    async def overflow() -> SendResult:
        return await asyncio.wait_for(
            messaging.service.send(
                notebook, MessageRequest(overflow_id, message, broadcast=True)
            ),
            1,
        )

    try:
        for _ in range(16):
            sends.append(
                await messaging.start(message=message, broadcast=True)
            )
        before = len(messaging.stream.records)
        with pytest.raises(ValueError, match="64 MB"):
            await overflow()
        await asyncio.sleep(0)
        assert len(messaging.stream.records) == before
        pointers = [
            r["data"]["custom"]["data"]
            for r in messaging.stream.records
            if r.get("event") == "custom"
        ]
        first = pointers[:2]
        assert first[0]["message_id"] == first[1]["message_id"]
        for index, pointer in enumerate(first):
            headers = (
                messaging.headers
                if pointer["agent_id"] == "k1"
                else {
                    **IDENTIFIED,
                    ATTACHMENT_HEADER: second.headers[
                        ATTACHMENT_HEADER.lower()
                    ],
                    REPORT_KEY_HEADER: second.headers[
                        REPORT_KEY_HEADER.lower()
                    ],
                }
            )
            response = await finished(
                h.app,
                "POST",
                messaging.path + f"/{pointer['attempt_id']}/content",
                headers=headers,
            )
            assert response.json()["message"] == message
            if index == 0:
                with pytest.raises(ValueError, match="64 MB"):
                    await overflow()
        accepted = asyncio.create_task(overflow())
        sends.append(accepted)
        await wait_for(messaging.stream, lambda r: len(r.records) > before)
        assert not accepted.done()
    finally:
        for send in sends:
            send.cancel()
        await asyncio.gather(*sends, return_exceptions=True)
        disconnect()
        await stream_task


async def test_duplicate_message_id_never_creates_another_attempt(
    messaging: MessagingRoutes,
) -> None:
    notebook = await messaging.harness.host.notebook(
        messaging.harness.notebook_id
    )
    send = await messaging.start()
    pointer = next(
        r["data"]["custom"]["data"]
        for r in messaging.stream.records
        if r.get("event") == "custom"
    )
    before = len(messaging.stream.records)
    try:
        for message_id in [
            pointer["message_id"],
            pointer["message_id"].upper(),
        ]:
            with pytest.raises(ValueError, match="Message ID"):
                await asyncio.wait_for(
                    messaging.service.send(
                        notebook,
                        MessageRequest(
                            message_id, "duplicate", broadcast=True
                        ),
                    ),
                    1,
                )
        await asyncio.sleep(0)
        assert len(messaging.stream.records) == before
        assert (await messaging.fetch()).json()["message"] == "private"
        assert (await messaging.report()).status == 204
        assert (await send).message_id == pointer["message_id"]
    finally:
        send.cancel()
        await asyncio.gather(send, return_exceptions=True)


async def test_oversize_message_emits_no_pointer(
    messaging: MessagingRoutes,
) -> None:
    notebook = await messaging.harness.host.notebook(
        messaging.harness.notebook_id
    )
    before = len(messaging.stream.records)
    with pytest.raises(ValueError, match="4 MB"):
        await messaging.service.send(
            notebook,
            MessageRequest(
                str(uuid4()), "x" * (4 * 1024 * 1024 - 1), broadcast=True
            ),
        )
    await asyncio.sleep(0)
    assert len(messaging.stream.records) == before
