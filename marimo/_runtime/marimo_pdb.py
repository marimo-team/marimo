# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import sys
from pdb import Pdb
from typing import TYPE_CHECKING, Any, Optional

from marimo import _loggers
from marimo._messaging.types import Stdin, Stdout

if TYPE_CHECKING:
    from types import FrameType, TracebackType

    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


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
