# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import inspect
import sys
from pdb import Pdb, Restart as pdbRestart
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._ast.compiler import cell_id_from_filename
from marimo._ast.variables import (
    if_local_then_mangle,
    is_local,
    is_mangled_local,
)
from marimo._messaging.types import Stdin, Stdout

if TYPE_CHECKING:
    from collections.abc import Iterable
    from types import FrameType, TracebackType

    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


def try_restart() -> bool:
    from marimo._runtime.commands import ExecuteCellsCommand
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
                cell_ids=[ctx.cell_id],
                codes=[graph.cells[ctx.cell_id].code],
            )
        )
    except ContextNotInitializedError:
        return False

    return True


def _defaults(args: ast.arguments) -> list[ast.expr]:
    """Default values, which are evaluated in the enclosing scope."""
    return [d for d in (*args.defaults, *args.kw_defaults) if d is not None]


def _names_bound_by(nodes: Iterable[ast.AST]) -> set[str]:
    """Every name the given scope binds, collected before it is visited.

    Python fixes a scope's locals for the whole body up front, so a reference
    can precede the binding. Bindings from scopes nested deeper still are
    folded in too: over-approximating here only leaves a name untouched, which
    is the safe direction.
    """
    names: set[str] = set()
    for node in nodes:
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(
                child.ctx, ast.Store
            ):
                names.add(child.id)
            elif isinstance(child, ast.arg):
                names.add(child.arg)
            elif isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                names.add(child.name)
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                names.update(
                    (alias.asname or alias.name).split(".")[0]
                    for alias in child.names
                )
            elif isinstance(child, ast.ExceptHandler) and child.name:
                names.add(child.name)
    return names


class _CellLocalMangler(ast.NodeTransformer):
    """Rewrite a cell's local names to the mangled names they are stored under.

    Only rewrites a name when it doesn't already resolve in the frame and its
    mangled counterpart does, so genuine globals (e.g. an unaliased `from x
    import _`, which marimo leaves unmangled) keep shadowing the cell-local.

    Names bound by a scope the typed source introduces itself (a `lambda`,
    `def` or comprehension) belong to that scope, not to the cell, and are
    left alone. That matches how cell code is compiled: marimo only mangles
    locals that resolve against the cell's top-level scope.
    """

    def __init__(self, cell_id: CellId_t, frame: FrameType) -> None:
        self.cell_id = cell_id
        self.frame = frame
        self.mangled = False
        self._nested_scopes: list[set[str]] = []

    def _defined(self, name: str) -> bool:
        return name in self.frame.f_locals or name in self.frame.f_globals

    def _bound_by_nested_scope(self, name: str) -> bool:
        return any(name in scope for scope in self._nested_scopes)

    def _visit_scope(
        self,
        bound: set[str],
        outer: Iterable[ast.AST],
        inner: Iterable[ast.AST],
    ) -> None:
        """Visit a scope the typed source introduces.

        `outer` nodes are evaluated in the enclosing scope; `inner` nodes see
        the names the new scope binds. Names are rewritten in place, so the
        visit results don't need reassigning.
        """
        for node in outer:
            self.visit(node)
        self._nested_scopes.append(bound)
        try:
            for node in inner:
                self.visit(node)
        finally:
            self._nested_scopes.pop()

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if (
            not is_local(node.id)
            or is_mangled_local(node.id)
            or self._bound_by_nested_scope(node.id)
            or self._defined(node.id)
        ):
            return node
        mangled = if_local_then_mangle(node.id, self.cell_id)
        if self._defined(mangled):
            node.id = mangled
            self.mangled = True
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.Lambda:
        self._visit_scope(
            bound=_names_bound_by([node.args, node.body]),
            outer=_defaults(node.args),
            inner=[node.body],
        )
        return node

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        self._visit_scope(
            bound=_names_bound_by([node.args, *node.body]),
            outer=[*node.decorator_list, *_defaults(node.args)],
            inner=node.body,
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self._visit_function(node)
        return node

    def visit_AsyncFunctionDef(
        self, node: ast.AsyncFunctionDef
    ) -> ast.AsyncFunctionDef:
        self._visit_function(node)
        return node

    def _visit_comprehension(
        self,
        node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp,
        elements: list[ast.expr],
    ) -> None:
        first, *rest = node.generators
        self._visit_scope(
            bound=_names_bound_by([*node.generators, *elements]),
            # Only the outermost iterable is evaluated eagerly, in the
            # enclosing scope.
            outer=[first.iter],
            inner=[*elements, first.target, *first.ifs, *rest],
        )

    def visit_ListComp(self, node: ast.ListComp) -> ast.ListComp:
        self._visit_comprehension(node, [node.elt])
        return node

    def visit_SetComp(self, node: ast.SetComp) -> ast.SetComp:
        self._visit_comprehension(node, [node.elt])
        return node

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> ast.GeneratorExp:
        self._visit_comprehension(node, [node.elt])
        return node

    def visit_DictComp(self, node: ast.DictComp) -> ast.DictComp:
        self._visit_comprehension(node, [node.key, node.value])
        return node


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

    def _mangle_cell_locals(
        self, source: str, frame: FrameType | None = None
    ) -> str:
        """Rewrite cell-local names in debugger input to their real names.

        marimo mangles a cell's underscore-prefixed variables so they stay
        private to the cell (`_b` is stored as `_cell_<cell_id>_b`), which
        would otherwise leave the names the user wrote undefined at the
        debugger prompt. Rewriting them before pdb evaluates the input makes
        `p _b` work just like `p b`.

        Input that isn't valid Python, or that isn't being evaluated in a
        cell's frame, is handed to pdb untouched.
        """
        if frame is None:
            frame = getattr(self, "curframe", None)
        if frame is None:
            return source
        cell_id = cell_id_from_filename(frame.f_code.co_filename)
        if cell_id is None:
            return source
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source
        mangler = _CellLocalMangler(cell_id, frame)
        mangler.visit(tree)
        return ast.unparse(tree) if mangler.mangled else source

    def default(self, line: str) -> Any:
        """Evaluate a statement typed at the prompt, demangling cell locals."""
        # pdb strips a leading `!` before compiling; strip it here too so that
        # what's left parses as Python.
        bang, source = ("!", line[1:]) if line[:1] == "!" else ("", line)
        return super().default(bang + self._mangle_cell_locals(source))

    def _getval(self, arg: str) -> Any:
        """Evaluate an expression (`p`, `pp`, ...), demangling cell locals."""
        return super()._getval(self._mangle_cell_locals(arg))

    def _getval_except(self, arg: str, frame: FrameType | None = None) -> Any:
        """Evaluate an expression for `display`, demangling cell locals."""
        return super()._getval_except(
            self._mangle_cell_locals(arg, frame), frame
        )

    def cmdloop(self, intro: str | None = None) -> None:
        """Override to gracefully handle restarts."""
        try:
            super().cmdloop(intro)
        except pdbRestart:
            if not try_restart():
                LOGGER.warning("Unable to restart cell.")

    def do_run(self, arg: str) -> bool | None:
        """super.do_run raises an error AND manipulates sys.argv"""
        del arg  # unused
        raise pdbRestart

    do_restart = do_run

    def post_mortem_by_cell_id(self, cell_id: CellId_t) -> None:
        return self.post_mortem(t=self._last_tracebacks.get(cell_id))

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
