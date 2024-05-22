# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from marimo._ast.cell import CellId_t
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.mimetypes import KnownMimeType

if TYPE_CHECKING:
    from collections import deque
    from threading import Condition
    from typing import Optional

    from marimo._messaging.types import Stream

StreamT = Literal[CellChannel.STDERR, CellChannel.STDOUT, CellChannel.STDIN]

# Flush console outputs every 10ms
TIMEOUT_S = 0.01


@dataclass
class ConsoleMsg:
    stream: StreamT
    cell_id: CellId_t
    data: str
    mimetype: KnownMimeType


def _write_console_output(
    stream: Stream,
    stream_type: StreamT,
    cell_id: CellId_t,
    data: str,
    mimetype: KnownMimeType,
) -> None:
    from marimo._messaging.ops import CellOp

    CellOp(
        cell_id=cell_id,
        console=CellOutput(
            channel=stream_type,
            mimetype=mimetype,
            data=data,
        ),
    ).broadcast(stream)


def _can_merge_outputs(first: ConsoleMsg, second: ConsoleMsg) -> bool:
    return first.stream == second.stream and first.mimetype == second.mimetype


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
    if buffer and _can_merge_outputs(buffer[-1], console_output):
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

    # only have a non-None timer when there's at least one output buffered
    #
    # when the timer expires, all buffered outputs are flushed
    timer: Optional[float] = None

    outputs_buffered_per_cell: dict[CellId_t, list[ConsoleMsg]] = {}
    while True:
        with cv:
            # We wait for messages until the timer (if any) expires
            while timer is None or timer > 0:
                time_started_waiting = time.time()
                # if the timer is set or if the message queue is empty, wait;
                # otherwise, no timer is set but we received a message, so
                # process it
                if timer is not None or not msg_queue:
                    cv.wait(timeout=timer)
                while msg_queue:
                    _add_output_to_buffer(
                        msg_queue.popleft(), outputs_buffered_per_cell
                    )
                if outputs_buffered_per_cell and timer is None:
                    # start the timeout timer
                    timer = TIMEOUT_S
                elif timer is not None:
                    time_waited = time.time() - time_started_waiting
                    timer -= time_waited

        # the timer has expired: flush the outputs
        for cell_id, buffer in outputs_buffered_per_cell.items():
            for output in buffer:
                _write_console_output(
                    stream,
                    output.stream,
                    cell_id,
                    output.data,
                    output.mimetype,
                )
        outputs_buffered_per_cell = {}
        timer = None
