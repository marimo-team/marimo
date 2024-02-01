from typing import Any
from unittest.mock import MagicMock, patch

from marimo._utils.distributor import Distributor


@patch("asyncio.get_event_loop")
def test_start(mock_get_event_loop: Any) -> None:
    mock_get_event_loop.return_value = MagicMock()

    mock_connection = MagicMock()
    distributor = Distributor[str](mock_connection)

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
