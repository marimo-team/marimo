# Copyright 2026 Marimo. All rights reserved.
"""An Executor executes a single cell's body."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Protocol

from marimo._ast.cell import _is_coroutine
from marimo._ast.variables import demangle_locals_in_text
from marimo._runtime.exceptions import MarimoRuntimeException
from marimo._types.globals import MutableGlobals

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl


def _demangle_name_error(e: BaseException) -> None:
    """Rewrite a NameError's message to use the name the user wrote.

    Cell-local (underscore-prefixed) references are compiled to mangled
    names (`_cell_<id>_x`); when one is undefined, CPython's message
    exposes the mangled form. The `name` attribute is left untouched for
    downstream consumers that resolve it structurally.
    """
    if isinstance(e, NameError) and e.args:
        e.args = tuple(
            demangle_locals_in_text(arg) if isinstance(arg, str) else arg
            for arg in e.args
        )


def _strip_frame(e: BaseException, count: int = 1) -> None:
    """Drop the top `count` frames from `e.__traceback__`.

    Stops early if the traceback runs out — never strips the last
    frame, so we don't lose the only frame we have.
    """
    tb = e.__traceback__
    for _ in range(count):
        if tb is None or tb.tb_next is None:
            break
        tb = tb.tb_next
    e.__traceback__ = tb


class Executor(Protocol):
    """Body strategy: how to run a cell's body."""

    name: str

    def execute_cell(self, cell: CellImpl, glbls: MutableGlobals) -> Any: ...

    async def execute_cell_async(
        self, cell: CellImpl, glbls: MutableGlobals
    ) -> Any: ...


class DefaultExecutor:
    name = "default"

    def execute_cell(self, cell: CellImpl, glbls: MutableGlobals) -> Any:
        if cell.body is None:
            return None
        assert cell.last_expr is not None
        if _is_coroutine(cell.body) or _is_coroutine(cell.last_expr):
            raise RuntimeError(
                "A coroutine cell cannot be run synchronously. Use "
                "execute_cell_async() instead."
            )
        try:
            exec(cell.body, glbls)
            return eval(cell.last_expr, glbls)
        except asyncio.CancelledError:
            # Cancellation is control flow, not user error — surface bare.
            raise
        except BaseException as e:
            # Strip our own frame so user-facing tracebacks start at user code.
            _strip_frame(e)
            _demangle_name_error(e)
            raise MarimoRuntimeException from e

    async def execute_cell_async(
        self, cell: CellImpl, glbls: MutableGlobals
    ) -> Any:
        if cell.body is None:
            return None
        assert cell.last_expr is not None
        try:
            if _is_coroutine(cell.body):
                await eval(cell.body, glbls)
            else:
                exec(cell.body, glbls)
            if _is_coroutine(cell.last_expr):
                return await eval(cell.last_expr, glbls)
            return eval(cell.last_expr, glbls)
        except asyncio.CancelledError:
            raise
        except BaseException as e:
            _strip_frame(e)
            _demangle_name_error(e)
            raise MarimoRuntimeException from e
