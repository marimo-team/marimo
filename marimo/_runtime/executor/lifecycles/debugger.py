# Copyright 2026 Marimo. All rights reserved.
"""DebuggerLifecycle frame-watches each cell body for the live debugger."""

from __future__ import annotations

import sys
import threading
from typing import TYPE_CHECKING, Any

from marimo._ast.compiler import cell_id_from_filename

if TYPE_CHECKING:
    from types import FrameType

    from marimo._ast.cell import CellImpl
    from marimo._messaging.types import Stream
    from marimo._runtime.executor.lifecycles import Skip
    from marimo._runtime.marimo_pdb import MarimoPdb
    from marimo._runtime.runner.result import RunResult
    from marimo._types.globals import MutableGlobals
    from marimo._types.ids import CellId_t


class FrameWatcher:
    """Frame watcher for the experimental live debugger.

    Installed around a single cell's execution (via `DebuggerLifecycle`):
    `install()` registers a `sys.settrace` hook on the executing thread and
    starts a heartbeat thread; `uninstall()` removes both. While installed it
    traces only cell frames (identified by the cell id encoded in their
    `co_filename`, see `cell_id_from_filename`) and:

    - records the current `(cell_id, line)` on every traced line (cheap), which
      the heartbeat flushes to the frontend as a `DebuggerLineNotification`
      only when it changes — never once per line; and
    - drops into `MarimoPdb` when a line with a registered breakpoint is hit,
      handing tracing off to pdb for the rest of the cell.

    `settrace` is per-thread, so only the cell-executing thread is traced. The
    heartbeat runs on its own thread (it must emit even while a synchronous
    cell blocks the kernel thread) using a stream copied for cross-thread use.
    """

    # Lines are flushed to the frontend at most this often.
    HEARTBEAT_INTERVAL_S = 0.075
    # Don't block teardown indefinitely waiting on the heartbeat thread.
    _JOIN_TIMEOUT_S = 1.0

    def __init__(self, debugger: MarimoPdb) -> None:
        self._debugger = debugger
        self._installed = False
        self._prev_trace: Any = None
        self._stream: Stream | None = None
        # Most recent (cell_id, line) seen by the trace function, and the last
        # value flushed to the frontend.
        self._current: tuple[CellId_t, int] | None = None
        self._flushed: tuple[CellId_t, int] | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # Cache co_filename -> cell_id to avoid re-parsing on every line.
        self._cell_id_cache: dict[str, CellId_t | None] = {}

    def install(self) -> None:
        if self._installed:
            return
        from marimo._runtime.context import get_context
        from marimo._runtime.context.types import ContextNotInitializedError

        try:
            stream = get_context().stream
            self._stream = stream.copy_for_thread()
        except (ContextNotInitializedError, RuntimeError):
            # No context (shouldn't happen during a cell run) or a stream that
            # can't be used off-thread; fall back to no line streaming.
            self._stream = None

        self._installed = True
        self._current = None
        self._flushed = None
        self._stop.clear()
        self._prev_trace = sys.gettrace()
        if self._stream is not None:
            self._thread = threading.Thread(
                target=self._heartbeat,
                name="marimo-frame-watcher",
                daemon=True,
            )
            self._thread.start()
        sys.settrace(self._trace)

    def uninstall(self) -> None:
        if not self._installed:
            return
        self._installed = False
        sys.settrace(self._prev_trace)
        self._prev_trace = None
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._JOIN_TIMEOUT_S)
            self._thread = None
        # Clear the current-line highlight on the frontend.
        if self._current is not None:
            self._broadcast(self._current[0], None)
        self._current = None
        self._flushed = None

    def _cell_id_for(self, filename: str) -> CellId_t | None:
        if filename not in self._cell_id_cache:
            self._cell_id_cache[filename] = cell_id_from_filename(filename)
        return self._cell_id_cache[filename]

    def _trace(self, frame: FrameType, event: str, arg: Any) -> Any:
        del arg
        if event == "call":
            # Only descend into cell frames; everything else (marimo
            # internals, libraries) is skipped with no per-line overhead.
            return (
                self._trace
                if self._cell_id_for(frame.f_code.co_filename) is not None
                else None
            )
        if event == "line":
            cell_id = self._cell_id_for(frame.f_code.co_filename)
            if cell_id is None:
                return self._trace
            lineno = frame.f_lineno
            self._current = (cell_id, lineno)
            if lineno in self._debugger.breakpoints.get(cell_id, ()):
                # Hand control to pdb at this frame. Returning pdb's dispatch
                # (rather than our own trace) keeps the frame traced by pdb,
                # which `set_trace` also installed globally.
                self._debugger.set_trace(frame)
                return self._debugger.trace_dispatch
        return self._trace

    def _heartbeat(self) -> None:
        while not self._stop.wait(self.HEARTBEAT_INTERVAL_S):
            current = self._current
            if current is not None and current != self._flushed:
                self._flushed = current
                self._broadcast(current[0], current[1])

    def _broadcast(self, cell_id: CellId_t, line: int | None) -> None:
        if self._stream is None:
            return
        from marimo._messaging.notification import DebuggerLineNotification
        from marimo._messaging.notification_utils import broadcast_notification

        broadcast_notification(
            DebuggerLineNotification(cell_id=cell_id, line=line),
            stream=self._stream,
        )


class DebuggerLifecycle:
    """Install a frame watcher around a cell body for the live debugger.

    `setup` installs the watcher (`sys.settrace` + heartbeat) before the body
    runs; `teardown` removes it. The lifecycle only toggles the watcher per
    cell so debug mode can be turned on and off. Gated by the `debugger`
    experimental flag (see `Runner.__init__`).
    """

    name = "debugger"

    def __init__(self, debugger: MarimoPdb) -> None:
        self._watcher = FrameWatcher(debugger)

    def setup(self, cell: CellImpl, glbls: MutableGlobals) -> Skip | None:
        del cell, glbls
        self._watcher.install()
        return None

    def teardown(
        self,
        cell: CellImpl,
        glbls: MutableGlobals,
        run_result: RunResult,
    ) -> None:
        del cell, glbls, run_result
        self._watcher.uninstall()
