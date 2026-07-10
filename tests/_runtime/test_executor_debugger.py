# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import pytest

from tests._messaging.mocks import MockStream


class _FakeDebugger:
    """Minimal stand-in for `MarimoPdb` used by the frame watcher tests.

    Records `interaction()` calls (by line) instead of entering a real pdb
    session.
    """

    def __init__(
        self,
        *,
        quit_on_interaction: bool = False,
        step: bool = False,
    ) -> None:
        self.breakpoints: dict[Any, set[int]] = {}
        self.interaction_lines: list[int] = []
        self.nosigint = False
        self.quitting = False
        self.botframe: Any = None
        self._quit_on_interaction = quit_on_interaction
        # `step=True` mimics a `step`/`next` command: pdb wants to stop at
        # every upcoming line (`stop_here` truthy). Default mimics `continue`.
        self._step = step

    def disable_sigint(self) -> None:
        self.nosigint = True

    def reset(self) -> None:
        self.quitting = False

    def stop_here(self, frame: Any) -> bool:
        del frame
        return self._step

    def interaction(self, frame: Any, traceback: Any) -> None:
        del traceback
        self.interaction_lines.append(frame.f_lineno)
        # Mimic pdb's `quit` command setting the bdb quitting flag.
        if self._quit_on_interaction:
            self.quitting = True


class TestFrameWatcher:
    @staticmethod
    def _cell_code(cell_id: str, code: str) -> Any:
        from marimo._ast.compiler import get_filename

        return compile(code, get_filename(cell_id), "exec")

    @staticmethod
    def test_records_current_cell_line() -> None:
        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        watcher = FrameWatcher(_FakeDebugger())  # type: ignore[arg-type]
        code = TestFrameWatcher._cell_code("abc", "a = 1\nb = 2\nc = 3\n")
        watcher.install()
        try:
            exec(code, {})
            current = watcher._current
        finally:
            watcher.uninstall()
        assert current == ("abc", 3)

    @staticmethod
    def test_ignores_non_cell_frames() -> None:
        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        watcher = FrameWatcher(_FakeDebugger())  # type: ignore[arg-type]
        # A plain (non-cell) filename must never be traced.
        code = compile("a = 1\nb = 2\n", "<plain>", "exec")
        watcher.install()
        try:
            exec(code, {})
            current = watcher._current
        finally:
            watcher.uninstall()
        assert current is None

    @staticmethod
    def test_breakpoint_drops_into_pdb() -> None:
        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        debugger = _FakeDebugger()
        debugger.breakpoints = {"abc": {2}}
        watcher = FrameWatcher(debugger)  # type: ignore[arg-type]
        code = TestFrameWatcher._cell_code("abc", "a = 1\nb = 2\nc = 3\n")
        watcher.install()
        try:
            exec(code, {})
        finally:
            watcher.uninstall()
        # The pdb prompt opens once, at the breakpoint line, and not for
        # other lines.
        assert debugger.interaction_lines == [2]

    @staticmethod
    def test_breakpoint_in_loop_rehits_each_iteration() -> None:
        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        debugger = _FakeDebugger()
        # Line 2 (the loop body) has a breakpoint; it should fire on every
        # iteration even though `interaction` (continue) returns each time.
        debugger.breakpoints = {"abc": {2}}
        watcher = FrameWatcher(debugger)  # type: ignore[arg-type]
        code = TestFrameWatcher._cell_code(
            "abc", "for i in range(3):\n    x = i\n"
        )
        watcher.install()
        try:
            exec(code, {})
        finally:
            watcher.uninstall()
        assert debugger.interaction_lines == [2, 2, 2]

    @staticmethod
    def test_step_stops_at_each_following_line() -> None:
        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        # Breakpoint at line 1; stepping then stops at every subsequent line
        # (the watcher consults pdb's `stop_here` once a session is underway).
        debugger = _FakeDebugger(step=True)
        debugger.breakpoints = {"abc": {1}}
        watcher = FrameWatcher(debugger)  # type: ignore[arg-type]
        code = TestFrameWatcher._cell_code("abc", "a = 1\nb = 2\nc = 3\n")
        watcher.install()
        try:
            exec(code, {})
        finally:
            watcher.uninstall()
        assert debugger.interaction_lines == [1, 2, 3]

    @staticmethod
    def test_quit_stops_the_cell() -> None:
        from marimo._runtime.control_flow import MarimoStopError
        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        debugger = _FakeDebugger(quit_on_interaction=True)
        debugger.breakpoints = {"abc": {2}}
        watcher = FrameWatcher(debugger)  # type: ignore[arg-type]
        code = TestFrameWatcher._cell_code("abc", "a = 1\nb = 2\nc = 3\n")
        watcher.install()
        try:
            # Quitting at the breakpoint raises MarimoStopError out of the
            # cell body (the clean-stop path), so line 3 never runs.
            with pytest.raises(MarimoStopError):
                exec(code, {})
        finally:
            watcher.uninstall()
        assert debugger.interaction_lines == [2]

    @staticmethod
    def test_disables_pdb_sigint_hijack() -> None:
        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        debugger = _FakeDebugger()
        watcher = FrameWatcher(debugger)  # type: ignore[arg-type]
        watcher.install()
        try:
            # marimo owns SIGINT, so pdb must not install its own handler.
            assert debugger.nosigint is True
        finally:
            watcher.uninstall()

    @staticmethod
    def test_uninstall_restores_previous_trace() -> None:
        import sys

        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        prev = sys.gettrace()
        watcher = FrameWatcher(_FakeDebugger())  # type: ignore[arg-type]
        watcher.install()
        # `_trace` is a bound method (new wrapper each access), so compare the
        # underlying instance rather than identity.
        installed = sys.gettrace()
        assert getattr(installed, "__self__", None) is watcher
        watcher.uninstall()
        assert sys.gettrace() is prev

    @staticmethod
    def test_broadcast_emits_active_line_notification() -> None:
        from marimo._messaging.notification import ActiveLineNotification
        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        watcher = FrameWatcher(_FakeDebugger())  # type: ignore[arg-type]
        watcher._stream = MockStream()
        watcher._broadcast("abc", 5)  # type: ignore[arg-type]
        watcher._broadcast("abc", None)  # type: ignore[arg-type]

        ops = watcher._stream.parsed_operations
        assert len(ops) == 2
        assert isinstance(ops[0], ActiveLineNotification)
        assert ops[0].cell_id == "abc"
        assert ops[0].line == 5
        assert ops[1].line is None


class TestFrameWatcherWithoutDebugger:
    """The watcher with `debugger=None` (the `line_timing` flag) only streams
    the active line; there is no pdb to enter."""

    @staticmethod
    def test_records_current_cell_line() -> None:
        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        watcher = FrameWatcher(None)
        code = TestFrameWatcher._cell_code("abc", "a = 1\nb = 2\nc = 3\n")
        watcher.install()
        try:
            exec(code, {})
            current = watcher._current
        finally:
            watcher.uninstall()
        assert current == ("abc", 3)

    @staticmethod
    def test_install_uninstall_restores_previous_trace() -> None:
        import sys

        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        prev = sys.gettrace()
        watcher = FrameWatcher(None)
        watcher.install()
        installed = sys.gettrace()
        assert getattr(installed, "__self__", None) is watcher
        watcher.uninstall()
        assert sys.gettrace() is prev

    @staticmethod
    def test_runs_to_completion_without_entering_pdb() -> None:
        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        watcher = FrameWatcher(None)
        code = TestFrameWatcher._cell_code(
            "abc", "total = 0\nfor i in range(3):\n    total += i\n"
        )
        glbls: dict[str, Any] = {}
        watcher.install()
        try:
            exec(code, glbls)
        finally:
            watcher.uninstall()
        assert glbls["total"] == 3

    @staticmethod
    def test_heartbeat_flushes_active_line() -> None:
        import threading
        import time

        from marimo._messaging.notification import ActiveLineNotification
        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        watcher = FrameWatcher(None)
        stream = MockStream()
        watcher._stream = stream
        watcher._current = ("abc", 5)  # type: ignore[assignment]
        watcher._stop.clear()
        thread = threading.Thread(target=watcher._heartbeat, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if stream.parsed_operations:
                    break
                time.sleep(0.01)
        finally:
            watcher._stop.set()
            thread.join(timeout=1.0)

        ops = stream.parsed_operations
        assert ops, "heartbeat never flushed the active line"
        assert isinstance(ops[0], ActiveLineNotification)
        assert (ops[0].cell_id, ops[0].line) == ("abc", 5)
        assert watcher._flushed == ("abc", 5)

    @staticmethod
    def test_uninstall_broadcasts_line_clear() -> None:
        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        watcher = FrameWatcher(None)
        code = TestFrameWatcher._cell_code("abc", "a = 1\n")
        watcher.install()
        # No runtime context in tests, so install() found no stream; give the
        # watcher one to observe the clear broadcast on uninstall.
        stream = MockStream()
        watcher._stream = stream
        try:
            exec(code, {})
        finally:
            watcher.uninstall()

        assert stream.parsed_operations
        assert stream.parsed_operations[-1].line is None
