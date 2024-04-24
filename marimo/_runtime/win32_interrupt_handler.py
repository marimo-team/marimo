# Copyright 2024 Marimo. All rights reserved.
import queue
import signal
import threading
from _thread import interrupt_main
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from multiprocessing import Queue


class Win32InterruptHandler(threading.Thread):
    def __init__(self, interrupt_queue: "Queue[bool]") -> None:
        super(Win32InterruptHandler, self).__init__()
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
