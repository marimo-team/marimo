# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.mimetypes import ConsoleMimeType
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    import threading
    from collections import deque
    from threading import Condition

    from marimo._messaging.types import Stream

StreamT = Literal[CellChannel.STDERR, CellChannel.STDOUT, CellChannel.STDIN]

# Flush console outputs every 10ms
TIMEOUT_S = 0.01


@dataclass
class ConsoleMsg:
    stream: StreamT
    cell_id: CellId_t
    data: str
    mimetype: ConsoleMimeType


@dataclass
class FlushRequest:
    """Signal the buffered writer to flush pending outputs immediately.

    When the worker pops this off its queue, it drains whatever it has
    buffered to the underlying stream before setting ``done``. Callers can
    then be certain that every console message enqueued before this request
    has been written to the pipe.
    """

    done: threading.Event


def _write_console_output(
    stream: Stream,
    stream_type: StreamT,
    cell_id: CellId_t,
    data: str,
    mimetype: ConsoleMimeType,
) -> None:
    from marimo._messaging.notification import CellNotification
    from marimo._messaging.notification_utils import broadcast_notification

    broadcast_notification(
        CellNotification(
            cell_id=cell_id,
            console=CellOutput(
                channel=stream_type,
                mimetype=mimetype,
                data=data,
            ),
        ),
        stream,
    )


def _can_merge_outputs(first: ConsoleMsg, second: ConsoleMsg) -> bool:
    return first.stream == second.stream and first.mimetype == second.mimetype


def _add_output_to_buffer(
    console_output: ConsoleMsg,
    outputs_buffered_per_cell: dict[CellId_t, list[ConsoleMsg]],
) -> None:
    cell_id = console_output.cell_id
    buffer = outputs_buffered_per_cell.get(cell_id, None)
    if buffer and _can_merge_outputs(buffer[-1], console_output):
        buffer[-1].data += console_output.data
    elif buffer:
        buffer.append(console_output)
    else:
        outputs_buffered_per_cell[cell_id] = [console_output]


def buffered_writer(
    msg_queue: deque[ConsoleMsg | FlushRequest | None],
    stream: Stream,
    cv: Condition,
) -> None:
    """
    Writes standard out and standard error to frontend in batches

    Buffers console messages, writing them out in batches. A condition
    variable is used to synchronize access to `msg_queue`, and to obtain
    notifications when messages have been added. (A deque + condition variable
    was noticeably faster than the builtin queue.Queue in testing.)

    A `None` passed to `msg_queue` signals the writer should terminate;
    any still-buffered outputs are flushed before returning so that
    shutdown doesn't silently drop messages.

    A `FlushRequest` passed to `msg_queue` forces an immediate flush of
    whatever is currently buffered, and signals the request's `done` event
    once the outputs have been written to the stream.
    """

    # only have a non-None timer when there's at least one output buffered
    #
    # when the timer expires, all buffered outputs are flushed
    timer: float | None = None

    outputs_buffered_per_cell: dict[CellId_t, list[ConsoleMsg]] = {}
    pending_flush_requests: list[FlushRequest] = []
    terminating = False
    while True:
        with cv:
            # We wait for messages until the timer (if any) expires, or until
            # a flush/termination request forces us out of the wait loop.
            while timer is None or timer > 0:
                time_started_waiting = time.time()
                # if the timer is set or if the message queue is empty, wait;
                # otherwise, no timer is set but we received a message, so
                # process it
                if timer is not None or not msg_queue:
                    cv.wait(timeout=timer)
                while msg_queue:
                    msg = msg_queue.popleft()
                    if msg is None:
                        terminating = True
                    elif isinstance(msg, FlushRequest):
                        pending_flush_requests.append(msg)
                    else:
                        _add_output_to_buffer(msg, outputs_buffered_per_cell)
                if terminating or pending_flush_requests:
                    break
                if outputs_buffered_per_cell and timer is None:
                    # start the timeout timer
                    timer = TIMEOUT_S
                elif timer is not None:
                    time_waited = time.time() - time_started_waiting
                    timer -= time_waited

        # the timer has expired, a flush was requested, or we are shutting
        # down: write all buffered outputs to the stream
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

        # Signal any flush waiters only after writes have completed, so they
        # can rely on the invariant "pending outputs are on the pipe."
        for req in pending_flush_requests:
            req.done.set()
        pending_flush_requests = []

        if terminating:
            return
