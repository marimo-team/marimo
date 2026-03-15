from __future__ import annotations

import queue
import time
from typing import Any
from unittest.mock import MagicMock, patch

from marimo._utils.distributor import (
    ConnectionDistributor,
    QueueDistributor,
)


@patch("asyncio.get_event_loop")
def test_start(mock_get_event_loop: Any) -> None:
    mock_get_event_loop.return_value = MagicMock()

    mock_connection = MagicMock()
    distributor = ConnectionDistributor[str](mock_connection)

    # Define two mock consumer functions
    mock_consumer1 = MagicMock()
    mock_consumer2 = MagicMock()

    # Add the consumers to the distributor
    distributor.add_consumer(mock_consumer1)
    distributor.add_consumer(mock_consumer2)

    distributor.start()

    # Send
    mock_connection.recv.side_effect = ["test message"]
    mock_connection.poll.return_value = True
    distributor._on_change()

    # Assert both consumers received the message
    mock_consumer1.assert_called_once_with("test message")
    mock_consumer2.assert_called_once_with("test message")

    # Remove one of the consumers
    distributor.consumers.remove(mock_consumer1)

    # Distribute another message
    mock_consumer1.reset_mock()
    mock_consumer2.reset_mock()

    # Send
    mock_connection.recv.side_effect = ["test message"]
    mock_connection.poll.return_value = True
    distributor._on_change()

    # Assert only one consumer received the message
    mock_consumer1.assert_not_called()
    mock_consumer2.assert_called_once_with("test message")

    # Assert the event loop had the reader removed
    distributor.stop()
    assert mock_connection.closed


def test_queued_distributor() -> None:
    q = queue.Queue()
    distributor = QueueDistributor[str](q)

    # Define two mock consumer functions
    l1 = []
    l2 = []
    consumer1 = lambda msg: l1.append(msg)  # noqa: E731
    consumer2 = lambda msg: l2.append(msg)  # noqa: E731

    # Add the consumers to the distributor
    dispose = distributor.add_consumer(consumer1)
    distributor.add_consumer(consumer2)

    thread = distributor.start()

    q.put("msg1")
    q.put("msg2")

    waited_s = 0
    while not q.empty and waited_s < 2.0:
        time.sleep(0.1)
        waited_s += 0.1
    assert q.empty
    time.sleep(0.1)
    assert q.empty
    assert l1 == ["msg1", "msg2"]
    assert l2 == ["msg1", "msg2"]

    # Remove one of the consumers
    dispose()
    time.sleep(0.1)
    assert distributor._consumers == [consumer2]

    # Send
    q.put_nowait("msg3")

    waited_s = 0
    while not q.empty and waited_s < 2.0:
        time.sleep(0.1)
        waited_s += 0.1
    assert q.empty
    time.sleep(0.1)
    # l1 should not have gotten another message, it was removed
    assert l1 == ["msg1", "msg2"]
    assert l2 == ["msg1", "msg2", "msg3"]

    distributor.stop()
    thread.join(timeout=1.0)
    assert not thread.is_alive()


def test_queued_distributor_clears_consumers_on_stop() -> None:
    """Consumers must be cleared when the loop exits to release captured
    references (e.g. session closures that keep large data alive)."""
    q: queue.Queue[str | None] = queue.Queue()
    distributor = QueueDistributor[str](q)

    captured: list[str] = []
    distributor.add_consumer(lambda msg: captured.append(msg))
    assert len(distributor._consumers) == 1

    thread = distributor.start()

    # Send a message and give the loop time to deliver it before stopping.
    q.put("hello")
    time.sleep(0.2)
    distributor.stop()
    thread.join(timeout=2.0)
    assert not thread.is_alive()

    # Consumer list should have been cleared by the loop exit
    assert distributor._consumers == []
    # The message was delivered before stop
    assert captured == ["hello"]


def test_queued_distributor_stop_sets_flag() -> None:
    """stop() should set _stop flag and send None sentinel."""
    q: queue.Queue[str | None] = queue.Queue()
    distributor = QueueDistributor[str](q)

    assert distributor._stop is False
    distributor.stop()
    assert distributor._stop is True
    # None sentinel should be in the queue
    assert q.get_nowait() is None


def test_queued_distributor_restart_after_stop() -> None:
    """A distributor can be restarted on the same queue after stop().

    stop() may leave a None sentinel on the queue due to the _stop flag
    winning the race. start() must drain those sentinels and reset _stop
    so the new loop works correctly.
    """
    q: queue.Queue[str | None] = queue.Queue()
    distributor = QueueDistributor[str](q)

    # First run
    captured1: list[str] = []
    distributor.add_consumer(lambda msg: captured1.append(msg))
    thread1 = distributor.start()
    q.put("round1")
    time.sleep(0.2)
    distributor.stop()
    thread1.join(timeout=2.0)
    assert not thread1.is_alive()
    assert captured1 == ["round1"]

    # Restart on the same queue -- leftover None sentinel must not
    # cause the new loop to exit immediately.
    captured2: list[str] = []
    distributor.add_consumer(lambda msg: captured2.append(msg))
    thread2 = distributor.start()
    q.put("round2")
    time.sleep(0.2)
    assert captured2 == ["round2"]

    distributor.stop()
    thread2.join(timeout=2.0)
    assert not thread2.is_alive()


def test_queued_distributor_drain_sentinels_preserves_messages() -> None:
    """_drain_sentinels removes None values but preserves real messages."""
    q: queue.Queue[str | None] = queue.Queue()
    q.put("keep1")
    q.put(None)
    q.put("keep2")
    q.put(None)

    distributor = QueueDistributor[str](q)
    distributor._drain_sentinels()

    # Real messages should still be on the queue, None values removed
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    assert items == ["keep1", "keep2"]
