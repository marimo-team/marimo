# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import queue
import signal
import threading
from _thread import interrupt_main
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._session.queue import QueueType


class Win32InterruptHandler(threading.Thread):
    def __init__(self, interrupt_queue: QueueType[bool]) -> None:
        super().__init__()
        self.daemon = True
        self.interrupt_queue = interrupt_queue

    def run(self) -> None:
        while True:
            self.interrupt_queue.get()
            try:
                while self.interrupt_queue.get_nowait():
                    pass
            except queue.Empty:
                pass
            if callable(signal.getsignal(signal.SIGINT)):
                interrupt_main()
