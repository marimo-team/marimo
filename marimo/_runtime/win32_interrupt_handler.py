# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import queue
import signal
import sys
import threading
from _thread import interrupt_main
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._session.queue import QueueType


def ignore_console_ctrl_c() -> None:
    """Stop the Windows console from delivering Ctrl-C to this process.

    Terminal Ctrl-C belongs to the server; the kernel is interrupted via
    `Win32InterruptHandler` -> `interrupt_main()`, which still works after
    this (unlike `SIG_IGN`). See
    https://github.com/marimo-team/marimo/issues/4842.
    """
    if sys.platform != "win32":
        return
    import ctypes

    # Fails only if no console is attached, which is fine.
    ctypes.windll.kernel32.SetConsoleCtrlHandler(None, True)


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
