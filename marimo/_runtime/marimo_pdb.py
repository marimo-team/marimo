# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import sys
from pdb import Pdb, Restart as pdbRestart
from typing import TYPE_CHECKING, Any, Optional

from marimo import _loggers
from marimo._messaging.types import Stdin, Stdout

if TYPE_CHECKING:
    from types import FrameType, TracebackType

    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


def try_restart() -> bool:
    from marimo._runtime.context import (
        ContextNotInitializedError,
        get_context,
    )
    from marimo._runtime.context.kernel_context import (
        KernelRuntimeContext,
    )
    from marimo._runtime.requests import ExecuteMultipleRequest

    try:
        ctx = get_context()
        if ctx is None or not isinstance(ctx, KernelRuntimeContext):
            return False

        graph = ctx.graph
        if ctx.cell_id is None or ctx.cell_id not in graph.cells:
            return False

        # This runs the request and also runs UpdateCellCodes
        ctx._kernel.enqueue_control_request(
            ExecuteMultipleRequest(
                cell_ids=[ctx.cell_id],
                codes=[graph.cells[ctx.cell_id].code],
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
        self._last_traceback: Optional[TracebackType] = None

    def set_trace(
        self, frame: FrameType | None = None, header: str | None = None
    ) -> None:
        if header is not None:
            sys.stdout.write(header)
        return super().set_trace(frame)

    def cmdloop(self, intro: Optional[str] = None) -> None:
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

    def post_mortem(self, t: Optional[TracebackType] = None) -> None:
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
