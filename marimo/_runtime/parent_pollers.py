# Adapted from IPython/ipykernel
try:
    import ctypes
except Exception:
    ctypes = None
import os
import platform
import signal
import warnings
from _thread import interrupt_main
from threading import Thread


class ParentPollerWindows(Thread):
    """A Windows-specific daemon thread that listens for a special event that
    signals an interrupt and, optionally, terminates the program immediately
    when the parent process no longer exists.
    """

    def __init__(
        self,
        interrupt_handle: int | None = None,
        parent_handle: int | None = None,
    ) -> None:
        """Create the poller. At least one of the optional parameters must be
        provided.

        Parameters
        ----------
        interrupt_handle : HANDLE (int), optional
            If provided, the program will generate a Ctrl+C event when this
            handle is signaled.

        parent_handle : HANDLE (int), optional
            If provided, the program will terminate immediately when this
            handle is signaled.
        """
        assert interrupt_handle or parent_handle
        super(ParentPollerWindows, self).__init__()
        if ctypes is None:
            raise ImportError("ParentPollerWindows requires ctypes")
        self.daemon = True
        self.interrupt_handle = interrupt_handle
        self.parent_handle = parent_handle

    def run(self) -> None:
        """Run the poll loop. This method never returns."""
        try:
            from _winapi import INFINITE, WAIT_OBJECT_0
        except ImportError:
            from _subprocess import INFINITE, WAIT_OBJECT_0

        # Build the list of handle to listen on.
        handles = []
        print("HANDLE: ", self.interrupt_handle)
        if self.interrupt_handle:
            handles.append(self.interrupt_handle)
        if self.parent_handle:
            handles.append(self.parent_handle)
        arch = platform.architecture()[0]
        c_int = ctypes.c_int64 if arch.startswith("64") else ctypes.c_int

        # Listen forever.
        while True:
            #result = ctypes.windll.kernel32.WaitForMultipleObjects(
            #    len(handles),  # nCount
            #    (c_int * len(handles))(*handles),  # lpHandles
            #    False,  # bWaitAll
            #    INFINITE,
            #)  # dwMilliseconds
            result = ctypes.windll.kernel32.WaitForSingleObject(
                    c_int(handles[0]), INFINITE)
            

            if WAIT_OBJECT_0 <= result < len(handles):
                handle = handles[result - WAIT_OBJECT_0]

                print("GOT HANDLE ", handle)
                if handle == self.interrupt_handle:
                    print("INTERRUPTING MAIN")
                    # check if signal handler is callable
                    # to avoid 'int not callable' error (Python issue #23395)
                    if callable(signal.getsignal(signal.SIGINT)):
                        interrupt_main()

                elif handle == self.parent_handle:
                    os._exit(1)
            elif result < 0:
                # wait failed, just give up and stop polling.
                #print(ctypes.windll.kernel32.GetLastError())
                warnings.warn(
                    """Parent poll failed.  If the frontend dies,
                the kernel may be left running.  Please let us know
                about your system (bitness, Python, etc.) at
                ipython-dev@scipy.org"""
                )
                #return
