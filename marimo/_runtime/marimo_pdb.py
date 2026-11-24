# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import inspect
import sys
from pdb import Pdb, Restart as pdbRestart
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._ast.compiler import cell_id_from_filename
from marimo._ast.parse import ast_parse
from marimo._ast.variables import demangle_locals_in_text
from marimo._ast.visitor import ScopedVisitor
from marimo._messaging.streams import PdbInput
from marimo._messaging.types import Stdin, Stdout

if TYPE_CHECKING:
    from collections.abc import Mapping
    from types import FrameType, TracebackType

    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


class _FrameLocalsVisitor(ScopedVisitor):
    """Rewrite `_b` only when the frame binds `_cell_<id>_b` and not `_b`
    itself. Raw imports, comprehension and function locals, and names that
    the user typed in mangled form stay as typed.
    """

    def __init__(
        self, mangle_prefix: str, scopes: tuple[Mapping[str, Any], ...]
    ) -> None:
        super().__init__(mangle_prefix)
        self._scopes = scopes

    def _bound(self, name: str) -> bool:
        return any(name in scope for scope in self._scopes)

    def is_local(self, name: str) -> bool:
        return (
            super().is_local(name)
            and not self._bound(name)
            and self._bound(self._mangle(name))
        )


def try_restart() -> bool:
    from marimo._runtime.commands import (
        ExecuteCellCommand,
        ExecuteCellsCommand,
    )
    from marimo._runtime.context import (
        ContextNotInitializedError,
        get_context,
    )
    from marimo._runtime.context.kernel_context import (
        KernelRuntimeContext,
    )

    try:
        ctx = get_context()
        if ctx is None or not isinstance(ctx, KernelRuntimeContext):
            return False

        graph = ctx.graph
        if ctx.cell_id is None or ctx.cell_id not in graph.cells:
            return False

        # This runs the request and queues the cell for execution
        ctx._kernel.enqueue_control_request(
            ExecuteCellsCommand(
                execution_requests=[
                    ExecuteCellCommand(
                        cell_id=ctx.cell_id, code=graph.cells[ctx.cell_id].code
                    )
                ]
            )
        )
    except ContextNotInitializedError:
        return False

    return True


class MarimoPdb(Pdb):
    # Because we are patching Pdb, we need copy the exact constructor signature
    def __init__(
        self,
        completekey: str = "tab",
        stdout: Stdout | None = None,
        stdin: Stdin | None = None,
        skip: Any = None,
        nosigint: bool = False,
        readrc: bool = True,
    ):
        super().__init__(
            completekey=completekey,
            stdout=stdout,  # type: ignore[arg-type]
            stdin=stdin,  # type: ignore[arg-type]
            skip=skip,
            nosigint=nosigint,
            readrc=readrc,
        )  # type: ignore[arg-type]
        # it's fine to use input() since marimo overrides it, but disable
        # it anyway -- stdin is fine too ...
        self.use_rawinput = stdin is None

        # Some custom attributes to hold on to exception data from cell
        # evaluation.
        self._last_tracebacks: dict[CellId_t, TracebackType] = {}
        self._last_traceback: TracebackType | None = None

        # Live breakpoints, keyed by cell id -> set of 1-based line numbers.
        # Session-scoped (not persisted to the notebook file); updated by the
        # `SetBreakpointsCommand` handler and read by the frame watcher.
        self.breakpoints: dict[CellId_t, set[int]] = {}

    def disable_sigint(self) -> None:
        """Stop pdb from installing its own SIGINT handler.

        marimo owns interrupt handling; with pdb's handler installed an
        interrupt becomes a debugger break instead of interrupting the cell.
        """
        self.nosigint = True

    def set_trace(
        self, frame: FrameType | None = None, header: str | None = None
    ) -> None:
        if header is not None:
            sys.stdout.write(header)
        return super().set_trace(frame)

    def _mangle_cell_locals(self, source: str, frame: FrameType | None) -> str:
        """Mangle cell-local names in `source` to match the cell's code.

        If `frame` does not belong to a cell, or if `source` is not valid
        Python, `source` is returned unchanged.
        """
        if frame is None:
            return source
        cell_id = cell_id_from_filename(frame.f_code.co_filename)
        # Cell ids in an embedded app contain `-`, so their mangled names
        # cannot be typed at the prompt.
        if cell_id is None or not f"_cell_{cell_id}".isidentifier():
            return source
        # Before 3.13, a prompt assignment is lost if `f_locals` is read
        # again.
        local_names = (
            self.curframe_locals
            if sys.version_info < (3, 13) and frame is self.curframe
            else frame.f_locals
        )
        visitor = _FrameLocalsVisitor(
            "cell_" + cell_id, (local_names, frame.f_globals, frame.f_builtins)
        )
        try:
            tree = ast_parse(source)
            before = ast.dump(tree)
            visitor.visit(tree)
        except (SyntaxError, ValueError):
            return source
        if ast.dump(tree) == before:
            return source
        # pdb compiles a line in `single` mode, so `a = 1; _b = 2` must stay
        # on one line.
        return "; ".join(ast.unparse(stmt) for stmt in tree.body)

    def error(self, msg: object) -> None:
        # Show names as the user typed them. Some commands pass an
        # exception instead of a string.
        super().error(demangle_locals_in_text(str(msg)))

    def default(self, line: str) -> None:
        # Remove a leading `!` before parsing. pdb removes it too, but only
        # later.
        line = line.removeprefix("!").lstrip()
        super().default(self._mangle_cell_locals(line, self.curframe))

    def _getval(self, arg: str) -> Any:
        return super()._getval(self._mangle_cell_locals(arg, self.curframe))

    def _getval_except(self, arg: str, frame: FrameType | None = None) -> Any:
        source = self._mangle_cell_locals(arg, frame or self.curframe)
        return super()._getval_except(source, frame)

    def cmdloop(self, intro: str | None = None) -> None:
        """Override to gracefully handle restarts."""
        try:
            super().cmdloop(intro)
        except KeyboardInterrupt:
            # Returning lets pdb finish the interaction and release its frames.
            if not isinstance(self.stdin, PdbInput):
                raise
        except pdbRestart:
            if not try_restart():
                LOGGER.warning("Unable to restart cell.")

    def do_run(self, arg: str) -> bool | None:
        """super.do_run raises an error AND manipulates sys.argv"""
        del arg  # unused
        raise pdbRestart

    do_restart = do_run

    def post_mortem_by_cell_id(
        self, cell_id: CellId_t, *, stdin: PdbInput | None = None
    ) -> None:
        previous = self.stdin
        try:
            if stdin is not None:
                self.stdin = stdin
            self.post_mortem(t=self._last_tracebacks.get(cell_id))
        finally:
            self.stdin = previous

    def post_mortem(self, t: TracebackType | None = None) -> None:
        if t is None:
            t = self._last_traceback

        # Language and behavior copied from cpython.
        if t is None or (
            isinstance(t, BaseException) and t.__traceback__ is None
        ):
            raise ValueError(
                "A valid traceback must be passed if no "
                "exception is being handled"
            )

        self.reset()
        self.interaction(None, t)

    def do_interact(self, arg: Any) -> None:
        """Interact

        Catch interact to avoid SystemExit exceptions from hanging the kernel.
        """
        try:
            super().do_interact(arg)
        except SystemExit:
            pass


def set_trace(
    debugger: MarimoPdb,
    frame: FrameType | None = None,
    header: str | None = None,
) -> None:
    if frame is None:
        # make sure the frame points to user code
        current_frame = inspect.currentframe()
        frame = current_frame.f_back if current_frame is not None else None
    debugger.set_trace(frame, header=header)
