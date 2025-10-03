# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional

from marimo._messaging.cell_output import CellChannel
from marimo._messaging.console_output_worker import (
    TIMEOUT_S,
    ConsoleMsg,
    _add_output_to_buffer,
    _can_merge_outputs,
    _write_console_output,
    buffered_writer,
)
from tests._messaging.mocks import MockStream


class TestConsoleOutputWorker:
    def test_can_merge_outputs(self) -> None:
        # Same stream and mimetype should be mergeable
        msg1 = ConsoleMsg(
            stream=CellChannel.STDOUT,
            cell_id="cell1",
            data="Hello",
            mimetype="text/plain",
        )
        msg2 = ConsoleMsg(
            stream=CellChannel.STDOUT,
            cell_id="cell1",
            data=" World",
            mimetype="text/plain",
        )
        assert _can_merge_outputs(msg1, msg2) is True

        # Different stream should not be mergeable
        msg3 = ConsoleMsg(
            stream=CellChannel.STDERR,
            cell_id="cell1",
            data="Error",
            mimetype="text/plain",
        )
        assert _can_merge_outputs(msg1, msg3) is False

        # Different mimetype should not be mergeable
        msg4 = ConsoleMsg(
            stream=CellChannel.STDOUT,
            cell_id="cell1",
            data="<h1>Hello</h1>",
            mimetype="text/html",
        )
        assert _can_merge_outputs(msg1, msg4) is False

    def test_add_output_to_buffer_new_cell(self) -> None:
        # Test adding output for a new cell
        outputs_buffered_per_cell = {}
        msg = ConsoleMsg(
            stream=CellChannel.STDOUT,
            cell_id="cell1",
            data="Hello",
            mimetype="text/plain",
        )

        _add_output_to_buffer(msg, outputs_buffered_per_cell)

        assert "cell1" in outputs_buffered_per_cell
        assert len(outputs_buffered_per_cell["cell1"]) == 1
        assert outputs_buffered_per_cell["cell1"][0].data == "Hello"

    def test_add_output_to_buffer_merge(self) -> None:
        # Test merging output for an existing cell with same stream and mimetype
        outputs_buffered_per_cell = {
            "cell1": [
                ConsoleMsg(
                    stream=CellChannel.STDOUT,
                    cell_id="cell1",
                    data="Hello",
                    mimetype="text/plain",
                )
            ]
        }
        msg = ConsoleMsg(
            stream=CellChannel.STDOUT,
            cell_id="cell1",
            data=" World",
            mimetype="text/plain",
        )

        _add_output_to_buffer(msg, outputs_buffered_per_cell)

        assert len(outputs_buffered_per_cell["cell1"]) == 1
        assert outputs_buffered_per_cell["cell1"][0].data == "Hello World"

    def test_add_output_to_buffer_no_merge(self) -> None:
        # Test adding output for an existing cell with different stream or mimetype
        outputs_buffered_per_cell = {
            "cell1": [
                ConsoleMsg(
                    stream=CellChannel.STDOUT,
                    cell_id="cell1",
                    data="Hello",
                    mimetype="text/plain",
                )
            ]
        }
        msg = ConsoleMsg(
            stream=CellChannel.STDERR,
            cell_id="cell1",
            data="Error",
            mimetype="text/plain",
        )

        _add_output_to_buffer(msg, outputs_buffered_per_cell)

        assert len(outputs_buffered_per_cell["cell1"]) == 2
        assert outputs_buffered_per_cell["cell1"][0].data == "Hello"
        assert outputs_buffered_per_cell["cell1"][1].data == "Error"

    def test_write_console_output(self) -> None:
        # Test writing console output to stream
        stream = MockStream()
        _write_console_output(
            stream,
            CellChannel.STDOUT,
            "cell1",
            "Hello",
            "text/plain",
        )

        assert len(stream.operations) == 1
        assert stream.operations[0]["op"] == "cell-op"
        assert stream.operations[0]["cell_id"] == "cell1"
        assert stream.operations[0]["console"]["channel"] == "stdout"
        assert stream.operations[0]["console"]["mimetype"] == "text/plain"
        assert stream.operations[0]["console"]["data"] == "Hello"

    def test_buffered_writer_basic(self) -> None:
        # Test basic functionality of buffered writer
        stream = MockStream()
        msg_queue: deque[Optional[ConsoleMsg]] = deque()
        cv = threading.Condition()

        # Start the buffered writer in a separate thread
        thread = threading.Thread(
            target=buffered_writer, args=(msg_queue, stream, cv)
        )
        thread.daemon = True
        thread.start()

        try:
            # Add a message to the queue
            with cv:
                msg_queue.append(
                    ConsoleMsg(
                        stream=CellChannel.STDOUT,
                        cell_id="cell1",
                        data="Hello",
                        mimetype="text/plain",
                    )
                )
                cv.notify()

            # Wait for the timeout to expire and the message to be written
            # Use a longer timeout to ensure the message is processed
            time.sleep(TIMEOUT_S * 5)

            for _ in range(10):
                time.sleep(0.1)
                if len(stream.operations) == 1:
                    break

            # Check that the message was written to the stream
            assert len(stream.operations) == 1
            assert stream.operations[0]["console"]["data"] == "Hello"

        finally:
            # Signal the writer to terminate
            with cv:
                msg_queue.append(None)
                cv.notify()
            thread.join(timeout=1.0)

    def test_buffered_writer_multiple_messages(self) -> None:
        # Test buffered writer with multiple messages
        stream = MockStream()
        msg_queue: deque[Optional[ConsoleMsg]] = deque()
        cv = threading.Condition()

        # Start the buffered writer in a separate thread
        thread = threading.Thread(
            target=buffered_writer, args=(msg_queue, stream, cv)
        )
        thread.daemon = True
        thread.start()

        try:
            # Add multiple messages to the queue
            with cv:
                msg_queue.append(
                    ConsoleMsg(
                        stream=CellChannel.STDOUT,
                        cell_id="cell1",
                        data="Hello",
                        mimetype="text/plain",
                    )
                )
                msg_queue.append(
                    ConsoleMsg(
                        stream=CellChannel.STDOUT,
                        cell_id="cell1",
                        data=" World",
                        mimetype="text/plain",
                    )
                )
                msg_queue.append(
                    ConsoleMsg(
                        stream=CellChannel.STDERR,
                        cell_id="cell1",
                        data="Error",
                        mimetype="text/plain",
                    )
                )
                cv.notify()

            # Wait for the timeout to expire and the messages to be written
            # Use a longer timeout to ensure the messages are processed
            time.sleep(TIMEOUT_S * 5)

            for _ in range(10):
                time.sleep(0.1)
                if len(stream.messages) == 2:
                    break

            # Check that the messages were written to the stream
            assert len(stream.messages) == 2  # Merged stdout messages + stderr

            # First message should be the merged stdout messages
            first_message = stream.operations[0]
            assert first_message["console"]["channel"] == "stdout"
            assert first_message["console"]["data"] == "Hello World"

            # Second message should be the stderr message
            second_message = stream.operations[1]
            assert second_message["console"]["channel"] == "stderr"
            assert second_message["console"]["data"] == "Error"

        finally:
            # Signal the writer to terminate
            with cv:
                msg_queue.append(None)
                cv.notify()
            thread.join(timeout=1.0)
