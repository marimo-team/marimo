# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from threading import Condition
from typing import TYPE_CHECKING, Literal, Optional

from marimo._ast.cell import CellId_t
from marimo._messaging.cell_output import CellOutput

if TYPE_CHECKING:
    from marimo._messaging.streams import Stream

StreamT = Literal["stdout", "stderr"]

# Flush console outputs every 10ms
TIMEOUT_S = 0.01


@dataclass
class ConsoleMsg:
    stream: StreamT
    cell_id: CellId_t
    data: str


def _write_console_output(
    stream: Stream, stream_type: StreamT, cell_id: CellId_t, data: str
) -> None:
    from marimo._messaging.ops import CellOp

    CellOp(
        cell_id=cell_id,
        console=CellOutput(
            channel=stream_type,
            mimetype="text/plain",
            data=data,
        ),
    ).broadcast(stream)


def _add_output_to_buffer(
    console_output: ConsoleMsg,
    outputs_buffered_per_cell: dict[CellId_t, list[ConsoleMsg]],
) -> None:
    cell_id = console_output.cell_id
    buffer = (
        outputs_buffered_per_cell[cell_id]
        if cell_id in outputs_buffered_per_cell
        else None
    )
    if buffer and buffer[-1].stream == console_output.stream:
        buffer[-1].data += console_output.data
    elif buffer:
        buffer.append(console_output)
    else:
        outputs_buffered_per_cell[cell_id] = [console_output]


def buffered_writer(
    msg_queue: deque[ConsoleMsg],
    stream: Stream,
    cv: Condition,
) -> None:
    """
    Writes standard out and standard error to frontend in batches

    Buffers console messages, writing them out in batches. A condition
    variable is used to synchronize access to `msg_queue`, and to obtain
    notifications when messages have been added. (A deque + condition variable
    was noticeably faster than the builtin queue.Queue in testing.)
    """

    # only have a non-None timeout when there's at least one output buffered
    timeout: Optional[float] = None
    outputs_buffered_per_cell: dict[CellId_t, list[ConsoleMsg]] = {}
    while True:
        with cv:
            # We wait for messages until we've timed-out
            while timeout is None or timeout > 0:
                time_started_waiting = time.time()
                # if we have at least one buffered output, wait for a finite
                # amount of time; otherwise, timeout is None and we wait
                # until we are notified.
                cv.wait(timeout=timeout)
                while msg_queue:
                    _add_output_to_buffer(
                        msg_queue.popleft(), outputs_buffered_per_cell
                    )
                if outputs_buffered_per_cell and timeout is None:
                    # start the timeout timer
                    timeout = TIMEOUT_S
                elif timeout is not None:
                    time_waited = time.time() - time_started_waiting
                    timeout -= time_waited

        # the timeout has expired
        for cell_id, buffer in outputs_buffered_per_cell.items():
            for output in buffer:
                _write_console_output(
                    stream, output.stream, cell_id, output.data
                )
        outputs_buffered_per_cell = {}
        timeout = None
