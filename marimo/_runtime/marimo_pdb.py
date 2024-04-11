# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import sys
from pdb import Pdb
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._messaging.types import Stdin, Stdout

if TYPE_CHECKING:
    from types import FrameType

LOGGER = _loggers.marimo_logger()


class MarimoPdb(Pdb):
    def __init__(self, stdout: Stdout | None, stdin: Stdin | None):
        super().__init__(stdout=stdout, stdin=stdin)  # type: ignore[arg-type]
        # it's fine to use input() since marimo overrides it, but disable
        # it anyway -- stdin is fine too ...
        self.use_rawinput = stdin is None

    def set_trace(
        self, frame: FrameType | None = None, header: str | None = None
    ) -> None:
        if header is not None:
            sys.stdout.write(header)
        return super().set_trace(frame)


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
