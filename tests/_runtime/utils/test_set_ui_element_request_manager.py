# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import queue
import threading
import time

from marimo._runtime.commands import (
    ModelCommand,
    ModelCustomMessage,
    ModelUpdateMessage,
    UpdateUIElementCommand,
)
from marimo._runtime.utils.set_ui_element_request_manager import (
    BatchableCommand,
    SetUIElementRequestManager,
    merge_batchable_commands,
)


def test_process_request_dedupes_by_token() -> None:
    """Test that duplicate tokens are properly deduplicated."""
    q: queue.Queue[BatchableCommand] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    # Create two requests with the same token
    request1 = UpdateUIElementCommand(
        object_ids=["obj1"], values=[1], token="token1"
    )
    request2 = UpdateUIElementCommand(
        object_ids=["obj2"], values=[2], token="token1"
    )

    # Put the duplicate in the queue
    q.put(request2)

    # Process the first request
    result = manager.process_request(request1)

    # Should only get one request (the second is a duplicate)
    assert len(result) == 1
    cmd = result[0]
    assert isinstance(cmd, UpdateUIElementCommand)
    assert len(cmd.object_ids) == 1
    assert cmd.object_ids[0] == "obj1"


def test_process_request_merges_different_tokens() -> None:
    """Test that requests with different tokens are merged."""
    q: queue.Queue[BatchableCommand] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    request1 = UpdateUIElementCommand(
        object_ids=["obj1"], values=[1], token="token1"
    )
    request2 = UpdateUIElementCommand(
        object_ids=["obj2"], values=[2], token="token2"
    )

    # Put the second request in the queue
    q.put(request2)

    # Process the first request
    result = manager.process_request(request1)

    # Should merge both requests
    assert len(result) == 1
    cmd = result[0]
    assert isinstance(cmd, UpdateUIElementCommand)
    assert len(cmd.object_ids) == 2
    assert set(cmd.object_ids) == {"obj1", "obj2"}


def test_process_request_keeps_latest_value_per_id() -> None:
    """Test that when multiple requests update the same UI element, the latest value wins."""
    q: queue.Queue[BatchableCommand] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    request1 = UpdateUIElementCommand(
        object_ids=["obj1"], values=[1], token="token1"
    )
    request2 = UpdateUIElementCommand(
        object_ids=["obj1"], values=[2], token="token2"
    )

    # Put the second request in the queue
    q.put(request2)

    # Process the first request
    result = manager.process_request(request1)

    # Should keep the latest value (from request2)
    assert len(result) == 1
    cmd = result[0]
    assert isinstance(cmd, UpdateUIElementCommand)
    assert len(cmd.object_ids) == 1
    assert cmd.object_ids[0] == "obj1"
    assert cmd.values[0] == 2


def test_process_request_handles_concurrent_queue_updates() -> None:
    """Test that the manager properly drains the queue even with concurrent updates.

    This simulates the race condition that occurs with ZeroMQ IPC where a
    receiver thread continuously adds messages to the queue.
    """
    q: queue.Queue[BatchableCommand] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    # Track how many requests were added
    requests_added = []
    stop_event = threading.Event()

    def producer():
        """Simulate a ZeroMQ receiver thread adding messages to the queue."""
        counter = 0
        while not stop_event.is_set():
            request = UpdateUIElementCommand(
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
    initial_request = UpdateUIElementCommand(
        object_ids=["obj_initial"], values=[999], token="token_initial"
    )

    result = manager.process_request(initial_request)

    # Stop the producer
    stop_event.set()
    producer_thread.join(timeout=1)

    # Verify that we got a merged result (all UI commands in a contiguous run)
    assert len(result) >= 1
    cmd = result[0]
    assert isinstance(cmd, UpdateUIElementCommand)
    assert len(cmd.object_ids) > 1  # Should have merged multiple requests
    assert "obj_initial" in cmd.object_ids

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
    q: asyncio.Queue[BatchableCommand] = asyncio.Queue()
    manager = SetUIElementRequestManager(q)

    request1 = UpdateUIElementCommand(
        object_ids=["obj1"], values=[1], token="token1"
    )
    request2 = UpdateUIElementCommand(
        object_ids=["obj2"], values=[2], token="token2"
    )

    # Put the second request in the queue
    q.put_nowait(request2)

    # Process the first request
    result = manager.process_request(request1)

    # Should merge both requests
    assert len(result) == 1
    cmd = result[0]
    assert isinstance(cmd, UpdateUIElementCommand)
    assert len(cmd.object_ids) == 2
    assert set(cmd.object_ids) == {"obj1", "obj2"}


def test_process_request_returns_empty_for_empty_batch() -> None:
    """Test that an empty list is returned when all requests are duplicates."""
    q: queue.Queue[BatchableCommand] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    # Create a request and process it
    request = UpdateUIElementCommand(
        object_ids=["obj1"], values=[1], token="token1"
    )
    result1 = manager.process_request(request)
    assert len(result1) == 1

    # Process the same token again (duplicate)
    result2 = manager.process_request(request)
    # Should return empty list since it's a duplicate
    assert result2 == []


# --- Model command tests ---


def test_model_update_merging_same_model() -> None:
    """Test that model updates for the same model merge with last-write-wins."""
    q: queue.Queue[BatchableCommand] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    cmd1 = ModelCommand(
        model_id="model-1",
        message=ModelUpdateMessage(state={"x": 1, "y": 2}, buffer_paths=[]),
        buffers=[],
    )
    cmd2 = ModelCommand(
        model_id="model-1",
        message=ModelUpdateMessage(state={"x": 10, "z": 3}, buffer_paths=[]),
        buffers=[],
    )
    q.put(cmd2)

    result = manager.process_request(cmd1)

    assert len(result) == 1
    cmd = result[0]
    assert isinstance(cmd, ModelCommand)
    assert cmd.model_id == "model-1"
    assert isinstance(cmd.message, ModelUpdateMessage)
    # x=10 from cmd2 (last-write-wins), y=2 from cmd1, z=3 from cmd2
    assert cmd.message.state == {"x": 10, "y": 2, "z": 3}


def test_model_update_different_models() -> None:
    """Test that updates to different models produce separate commands."""
    q: queue.Queue[BatchableCommand] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    cmd1 = ModelCommand(
        model_id="model-1",
        message=ModelUpdateMessage(state={"x": 1}, buffer_paths=[]),
        buffers=[],
    )
    cmd2 = ModelCommand(
        model_id="model-2",
        message=ModelUpdateMessage(state={"y": 2}, buffer_paths=[]),
        buffers=[],
    )
    q.put(cmd2)

    result = manager.process_request(cmd1)

    assert len(result) == 2
    ids = {r.model_id for r in result if isinstance(r, ModelCommand)}
    assert ids == {"model-1", "model-2"}


def test_custom_messages_pass_through() -> None:
    """Test that custom messages are not merged and each appears individually."""
    q: queue.Queue[BatchableCommand] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    cmd1 = ModelCommand(
        model_id="model-1",
        message=ModelCustomMessage(content={"action": "ping"}),
        buffers=[],
    )
    cmd2 = ModelCommand(
        model_id="model-1",
        message=ModelCustomMessage(content={"action": "pong"}),
        buffers=[],
    )
    q.put(cmd2)

    result = manager.process_request(cmd1)

    assert len(result) == 2
    assert all(isinstance(r, ModelCommand) for r in result)
    msgs = [r.message for r in result if isinstance(r, ModelCommand)]
    assert isinstance(msgs[0], ModelCustomMessage)
    assert isinstance(msgs[1], ModelCustomMessage)
    assert msgs[0].content == {"action": "ping"}
    assert msgs[1].content == {"action": "pong"}


def test_buffer_merging_drops_overridden_buffers() -> None:
    """Test that buffers for overridden state keys are dropped."""
    q: queue.Queue[BatchableCommand] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    cmd1 = ModelCommand(
        model_id="model-1",
        message=ModelUpdateMessage(
            state={"data": None},
            buffer_paths=[["data"]],
        ),
        buffers=[b"old-buffer"],
    )
    cmd2 = ModelCommand(
        model_id="model-1",
        message=ModelUpdateMessage(
            state={"data": None},
            buffer_paths=[["data"]],
        ),
        buffers=[b"new-buffer"],
    )
    q.put(cmd2)

    result = manager.process_request(cmd1)

    assert len(result) == 1
    cmd = result[0]
    assert isinstance(cmd, ModelCommand)
    assert isinstance(cmd.message, ModelUpdateMessage)
    # Only the new buffer should remain
    assert cmd.buffers == [b"new-buffer"]


def test_mixed_ui_and_model_commands() -> None:
    """Test that UI and model commands coexist in the result."""
    q: queue.Queue[BatchableCommand] = queue.Queue()
    manager = SetUIElementRequestManager(q)

    ui_cmd = UpdateUIElementCommand(
        object_ids=["obj1"], values=[1], token="token1"
    )
    model_cmd = ModelCommand(
        model_id="model-1",
        message=ModelUpdateMessage(state={"x": 1}, buffer_paths=[]),
        buffers=[],
    )
    q.put(model_cmd)

    result = manager.process_request(ui_cmd)

    assert len(result) == 2
    assert isinstance(result[0], UpdateUIElementCommand)
    assert isinstance(result[1], ModelCommand)


def test_contiguous_run_ordering() -> None:
    """Test that [UI, Model, UI] produces 3 items in that order, not grouped by type."""
    commands: list[BatchableCommand] = [
        UpdateUIElementCommand(
            object_ids=["obj1"], values=[1], token="token1"
        ),
        ModelCommand(
            model_id="model-1",
            message=ModelUpdateMessage(state={"x": 1}, buffer_paths=[]),
            buffers=[],
        ),
        UpdateUIElementCommand(
            object_ids=["obj2"], values=[2], token="token2"
        ),
    ]

    result = merge_batchable_commands(commands)

    assert len(result) == 3
    assert isinstance(result[0], UpdateUIElementCommand)
    assert isinstance(result[1], ModelCommand)
    assert isinstance(result[2], UpdateUIElementCommand)
    # Verify values preserved
    assert result[0].object_ids == ["obj1"]
    assert result[2].object_ids == ["obj2"]


def test_contiguous_runs_merged_within_run() -> None:
    """Test that contiguous same-type commands are merged within their run."""
    commands: list[BatchableCommand] = [
        UpdateUIElementCommand(
            object_ids=["obj1"], values=[1], token="token1"
        ),
        UpdateUIElementCommand(
            object_ids=["obj2"], values=[2], token="token2"
        ),
        ModelCommand(
            model_id="model-1",
            message=ModelUpdateMessage(state={"x": 1}, buffer_paths=[]),
            buffers=[],
        ),
        ModelCommand(
            model_id="model-1",
            message=ModelUpdateMessage(state={"x": 2}, buffer_paths=[]),
            buffers=[],
        ),
        UpdateUIElementCommand(
            object_ids=["obj3"], values=[3], token="token3"
        ),
    ]

    result = merge_batchable_commands(commands)

    # UI(merged) Model(merged) UI
    assert len(result) == 3
    assert isinstance(result[0], UpdateUIElementCommand)
    assert isinstance(result[1], ModelCommand)
    assert isinstance(result[2], UpdateUIElementCommand)

    # First UI run merged obj1 and obj2
    assert set(result[0].object_ids) == {"obj1", "obj2"}
    # Model run merged x=1 then x=2 → x=2
    assert isinstance(result[1].message, ModelUpdateMessage)
    assert result[1].message.state == {"x": 2}
    # Last UI is standalone
    assert result[2].object_ids == ["obj3"]
