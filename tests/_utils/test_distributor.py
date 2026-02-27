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
    assert distributor.consumers == [consumer2]

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
