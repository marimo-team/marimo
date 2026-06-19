# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from tests._messaging.mocks import MockStream


class _FakeDebugger:
    """Minimal stand-in for `MarimoPdb` used by the frame watcher tests.

    Records `set_trace` calls (by line) instead of entering a real pdb
    session, and exposes `trace_dispatch` so the watcher can hand off.
    """

    def __init__(self) -> None:
        self.breakpoints: dict[Any, set[int]] = {}
        self.set_trace_lines: list[int] = []

    def set_trace(self, frame: Any) -> None:
        self.set_trace_lines.append(frame.f_lineno)

    def trace_dispatch(self, *_args: Any) -> Any:
        return self.trace_dispatch


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
        # `set_trace` is called once, at the breakpoint line, and not for
        # other lines.
        assert debugger.set_trace_lines == [2]

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
    def test_broadcast_emits_debugger_line_notification() -> None:
        from marimo._messaging.notification import DebuggerLineNotification
        from marimo._runtime.executor.lifecycles.debugger import FrameWatcher

        watcher = FrameWatcher(_FakeDebugger())  # type: ignore[arg-type]
        watcher._stream = MockStream()
        watcher._broadcast("abc", 5)  # type: ignore[arg-type]
        watcher._broadcast("abc", None)  # type: ignore[arg-type]

        ops = watcher._stream.parsed_operations
        assert len(ops) == 2
        assert isinstance(ops[0], DebuggerLineNotification)
        assert ops[0].cell_id == "abc"
        assert ops[0].line == 5
        assert ops[1].line is None
