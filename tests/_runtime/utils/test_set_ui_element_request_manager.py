# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import queue
import threading
import time

from marimo._runtime.requests import SetUIElementValueRequest
from marimo._runtime.utils.set_ui_element_request_manager import (
    SetUIElementRequestManager,
)


def test_process_request_dedupes_by_token() -> None:
    """Test that duplicate tokens are properly deduplicated."""
    q: queue.Queue[SetUIElementValueRequest] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    # Create two requests with the same token
    request1 = SetUIElementValueRequest(
        object_ids=["obj1"], values=[1], token="token1"
    )
    request2 = SetUIElementValueRequest(
        object_ids=["obj2"], values=[2], token="token1"
    )

    # Put the duplicate in the queue
    q.put(request2)

    # Process the first request
    result = manager.process_request(request1)

    # Should only get one request (the second is a duplicate)
    assert result is not None
    assert len(result.object_ids) == 1
    assert result.object_ids[0] == "obj1"


def test_process_request_merges_different_tokens() -> None:
    """Test that requests with different tokens are merged."""
    q: queue.Queue[SetUIElementValueRequest] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    request1 = SetUIElementValueRequest(
        object_ids=["obj1"], values=[1], token="token1"
    )
    request2 = SetUIElementValueRequest(
        object_ids=["obj2"], values=[2], token="token2"
    )

    # Put the second request in the queue
    q.put(request2)

    # Process the first request
    result = manager.process_request(request1)

    # Should merge both requests
    assert result is not None
    assert len(result.object_ids) == 2
    assert set(result.object_ids) == {"obj1", "obj2"}


def test_process_request_keeps_latest_value_per_id() -> None:
    """Test that when multiple requests update the same UI element, the latest value wins."""
    q: queue.Queue[SetUIElementValueRequest] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    request1 = SetUIElementValueRequest(
        object_ids=["obj1"], values=[1], token="token1"
    )
    request2 = SetUIElementValueRequest(
        object_ids=["obj1"], values=[2], token="token2"
    )

    # Put the second request in the queue
    q.put(request2)

    # Process the first request
    result = manager.process_request(request1)

    # Should keep the latest value (from request2)
    assert result is not None
    assert len(result.object_ids) == 1
    assert result.object_ids[0] == "obj1"
    assert result.values[0] == 2


def test_process_request_handles_concurrent_queue_updates() -> None:
    """Test that the manager properly drains the queue even with concurrent updates.

    This simulates the race condition that occurs with ZeroMQ IPC where a
    receiver thread continuously adds messages to the queue.
    """
    q: queue.Queue[SetUIElementValueRequest] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    # Track how many requests were added
    requests_added = []
    stop_event = threading.Event()

    def producer():
        """Simulate a ZeroMQ receiver thread adding messages to the queue."""
        counter = 0
        while not stop_event.is_set():
            request = SetUIElementValueRequest(
                object_ids=[f"obj{counter}"],
                values=[counter],
                token=f"token{counter}",
            )
            q.put(request)
            requests_added.append(request)
            counter += 1
            time.sleep(0.001)  # Small delay to simulate real conditions

    # Start the producer thread
    producer_thread = threading.Thread(target=producer, daemon=True)
    producer_thread.start()

    # Let it produce some messages
    time.sleep(0.05)

    # Process a request while the producer is still running
    initial_request = SetUIElementValueRequest(
        object_ids=["obj_initial"], values=[999], token="token_initial"
    )

    result = manager.process_request(initial_request)

    # Stop the producer
    stop_event.set()
    producer_thread.join(timeout=1)

    # Verify that we got a merged result
    assert result is not None
    assert len(result.object_ids) > 1  # Should have merged multiple requests
    assert "obj_initial" in result.object_ids

    # Verify the queue is actually empty after processing
    # (small delay to let any in-flight messages arrive)
    time.sleep(0.01)
    remaining = []
    while not q.empty():
        try:
            remaining.append(q.get_nowait())
        except queue.Empty:
            break

    # There might be a few messages that arrived after we finished processing,
    # but it should be small compared to what we processed
    assert len(remaining) < 5  # Allow for a few stragglers


async def test_process_request_with_asyncio_queue() -> None:
    """Test that the manager works with asyncio.Queue."""
    q: asyncio.Queue[SetUIElementValueRequest] = asyncio.Queue()
    manager = SetUIElementRequestManager(q)

    request1 = SetUIElementValueRequest(
        object_ids=["obj1"], values=[1], token="token1"
    )
    request2 = SetUIElementValueRequest(
        object_ids=["obj2"], values=[2], token="token2"
    )

    # Put the second request in the queue
    q.put_nowait(request2)

    # Process the first request
    result = manager.process_request(request1)

    # Should merge both requests
    assert result is not None
    assert len(result.object_ids) == 2
    assert set(result.object_ids) == {"obj1", "obj2"}


def test_process_request_returns_none_for_empty_batch() -> None:
    """Test that None is returned when all requests are duplicates."""
    q: queue.Queue[SetUIElementValueRequest] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    # Create a request and process it
    request = SetUIElementValueRequest(
        object_ids=["obj1"], values=[1], token="token1"
    )
    result1 = manager.process_request(request)
    assert result1 is not None

    # Process the same token again (duplicate)
    result2 = manager.process_request(request)
    # Should return None since it's a duplicate
    assert result2 is None
