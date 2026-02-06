# Copyright 2026 Marimo. All rights reserved.
"""Queue manager implementation using multiprocessing or threading queues."""

from __future__ import annotations

import queue
import sys
from multiprocessing import get_context
from multiprocessing.queues import Queue as MPQueue
from typing import Optional, Union

from marimo._messaging.types import KernelMessage
from marimo._runtime import commands
from marimo._session.types import QueueManager


class QueueManagerImpl(QueueManager):
    """Manages queues for a session using multiprocessing or threading queues."""

    def __init__(self, *, use_multiprocessing: bool):
        context = get_context("spawn") if use_multiprocessing else None

        # Control messages for the kernel (run, set UI element, set config, etc
        # ) are sent through the control queue
        self.control_queue: Union[
            MPQueue[commands.CommandMessage],
            queue.Queue[commands.CommandMessage],
        ] = context.Queue() if context is not None else queue.Queue()

        # UI element updates and model commands are stored in both the
        # control queue and this queue, so that the backend can
        # merge/batch requests (last-write-wins per element/model ID).
        _BatchableCommand = Union[
            commands.UpdateUIElementCommand, commands.ModelCommand
        ]
        self.set_ui_element_queue: Union[
            MPQueue[_BatchableCommand],
            queue.Queue[_BatchableCommand],
        ] = context.Queue() if context is not None else queue.Queue()

        # Code completion requests are sent through a separate queue
        self.completion_queue: Union[
            MPQueue[commands.CodeCompletionCommand],
            queue.Queue[commands.CodeCompletionCommand],
        ] = context.Queue() if context is not None else queue.Queue()

        self.win32_interrupt_queue: (
            Union[MPQueue[bool], queue.Queue[bool]] | None
        )
        if sys.platform == "win32":
            self.win32_interrupt_queue = (
                context.Queue() if context is not None else queue.Queue()
            )
        else:
            self.win32_interrupt_queue = None

        # Input messages for the user's Python code are sent through the
        # input queue
        self.input_queue: Union[MPQueue[str], queue.Queue[str]] = (
            context.Queue(maxsize=1)
            if context is not None
            else queue.Queue(maxsize=1)
        )
        self.stream_queue: Optional[
            queue.Queue[Union[KernelMessage, None]]
        ] = None
        if not use_multiprocessing:
            self.stream_queue = queue.Queue()

    def close_queues(self) -> None:
        if isinstance(self.control_queue, MPQueue):
            # cancel join thread because we don't care if the queues still have
            # things in it: don't want to make the child process wait for the
            # queues to empty
            self.control_queue.cancel_join_thread()
            self.control_queue.close()
        else:
            # kernel thread cleans up read/write conn and IOloop handler on
            # exit; we don't join the thread because we don't want to block
            self.control_queue.put(commands.StopKernelCommand())

        if isinstance(self.set_ui_element_queue, MPQueue):
            self.set_ui_element_queue.cancel_join_thread()
            self.set_ui_element_queue.close()

        if isinstance(self.input_queue, MPQueue):
            # again, don't make the child process wait for the queues to empty
            self.input_queue.cancel_join_thread()
            self.input_queue.close()

        if isinstance(self.completion_queue, MPQueue):
            self.completion_queue.cancel_join_thread()
            self.completion_queue.close()

        if isinstance(self.win32_interrupt_queue, MPQueue):
            self.win32_interrupt_queue.cancel_join_thread()
            self.win32_interrupt_queue.close()

    def put_control_request(self, request: commands.CommandMessage) -> None:
        """Put a control request in the control queue."""
        # Completions are on their own queue
        if isinstance(request, commands.CodeCompletionCommand):
            self.completion_queue.put(request)
            return

        self.control_queue.put(request)
        # UI element updates and model commands are on both queues
        # so they can be batched
        if isinstance(
            request,
            (commands.UpdateUIElementCommand, commands.ModelCommand),
        ):
            self.set_ui_element_queue.put(request)

    def put_input(self, text: str) -> None:
        """Put an input request in the input queue."""
        self.input_queue.put(text)
