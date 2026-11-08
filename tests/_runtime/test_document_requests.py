# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import patch

import msgspec
import pytest

from marimo._core import protocol
from marimo._core.document import DocumentCell
from marimo._messaging.host import DocumentRequest, DocumentSnapshot
from marimo._messaging.types import KernelMessage
from marimo._runtime.commands import CommandMessage, DocumentReplyCommand
from marimo._runtime.document_requests import DocumentRequests

if TYPE_CHECKING:
    from marimo._runtime.runtime import Kernel


async def test_replies_can_arrive_out_of_order_from_another_thread() -> None:
    sent: asyncio.Queue[KernelMessage] = asyncio.Queue()
    requests = DocumentRequests(sent.put_nowait)
    first = asyncio.create_task(requests.request(DocumentRequest("first")))
    second = asyncio.create_task(requests.request(DocumentRequest("second")))
    assert [
        msgspec.json.decode(await sent.get(), type=DocumentRequest).request_id
        for _ in range(2)
    ] == ["first", "second"]
    replies = [
        DocumentReplyCommand(request_id="first"),
        DocumentReplyCommand(request_id="second"),
    ]
    await asyncio.to_thread(requests.receive, replies[1])
    await asyncio.to_thread(requests.receive, replies[0])
    assert await asyncio.gather(first, second) == replies


@pytest.mark.parametrize("cancel", [False, True])
async def test_abandoned_request_ignores_late_reply(cancel: bool) -> None:
    sent: asyncio.Queue[KernelMessage] = asyncio.Queue()
    requests = DocumentRequests(sent.put_nowait)
    task = asyncio.create_task(
        requests.request(
            DocumentRequest("request"), timeout=30 if cancel else 0
        )
    )
    await sent.get()
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
        await task
    requests.receive(DocumentReplyCommand(request_id="request"))
    retry = asyncio.create_task(requests.request(DocumentRequest("retry")))
    await sent.get()
    reply = DocumentReplyCommand(request_id="retry")
    requests.receive(reply)
    assert await retry == reply


async def test_close_releases_waiters_and_rejects_new_requests() -> None:
    sent: asyncio.Queue[KernelMessage] = asyncio.Queue()
    requests = DocumentRequests(sent.put_nowait)
    task = asyncio.create_task(requests.request(DocumentRequest("request")))
    await sent.get()
    await asyncio.to_thread(requests.close)
    with pytest.raises(RuntimeError, match="closed before replying"):
        await task
    with pytest.raises(RuntimeError, match="connection is closed"):
        await requests.request(DocumentRequest("next"))


async def test_duplicate_pending_id_does_not_replace_its_waiter() -> None:
    sent: asyncio.Queue[KernelMessage] = asyncio.Queue()
    requests = DocumentRequests(sent.put_nowait)
    request = DocumentRequest("request")
    task = asyncio.create_task(requests.request(request))
    await sent.get()
    with pytest.raises(ValueError, match="pending"):
        await requests.request(request)
    reply = DocumentReplyCommand(request_id="request")
    requests.receive(reply)
    assert await task == reply


async def test_kernel_dispatch_resolves_a_request_while_it_is_awaited(
    k: Kernel,
) -> None:
    sent: asyncio.Queue[KernelMessage] = asyncio.Queue()
    k.document_requests = DocumentRequests(sent.put_nowait)
    k.globals["host_requests"] = k.document_requests
    k.globals["host_request"] = DocumentRequest("request")
    task = asyncio.create_task(
        k.run_scratchpad(
            "reply = await host_requests.request(host_request)\n"
            "print(reply.request_id)"
        )
    )
    await sent.get()
    reply = DocumentReplyCommand(request_id="request")
    await asyncio.to_thread(k.dispatch_out_of_band, reply, docstrings_limit=5)
    await task
    assert str(k.stdout) == "request\n"


@pytest.mark.parametrize("binary", [False, True])
def test_snapshot_reply_round_trips_through_the_command_transport(
    binary: bool,
) -> None:
    document = DocumentSnapshot(
        cells=(DocumentCell(protocol.CellId("a"), "x = 1"),),
        app_config={"width": "full"},
    )
    reply = DocumentReplyCommand(request_id="request", document=document)
    codec = msgspec.msgpack if binary else msgspec.json
    assert codec.decode(codec.encode(reply), type=CommandMessage) == reply


@pytest.mark.parametrize("close", [False, True])
def test_loop_closing_during_delivery_does_not_escape_the_worker(
    close: bool,
) -> None:
    loop = asyncio.new_event_loop()
    requests = DocumentRequests(lambda _: None)
    future: asyncio.Future[DocumentReplyCommand] = loop.create_future()
    requests._pending["request"] = future

    def close_before_scheduling(*_args: object) -> None:
        loop.close()
        raise RuntimeError("Event loop is closed")

    try:
        with patch.object(
            loop, "call_soon_threadsafe", side_effect=close_before_scheduling
        ):
            if close:
                requests.close()
            else:
                requests.receive(DocumentReplyCommand(request_id="request"))
    finally:
        future.cancel()
        loop.close()
