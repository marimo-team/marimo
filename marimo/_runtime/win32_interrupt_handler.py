import queue
import signal
import threading
from _thread import interrupt_main

from multiprocessing import Queue


class Win32InterruptHandler(threading.Thread):
    def __init__(self, interrupt_queue: Queue) -> None:
        super(Win32InterruptHandler, self).__init__()
        self.daemon = True
        self.interrupt_queue = interrupt_queue

    def run(self):
        while True:
            self.interrupt_queue.get()
            print("got interrupt")
            try:
                while self.interrupt_queue.get_nowait():
                    pass
            except queue.Empty:
                pass
            if callable(signal.getsignal(signal.SIGINT)):
                print("interrupting main")
                interrupt_main()
