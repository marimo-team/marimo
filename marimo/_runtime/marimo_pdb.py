# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
from pdb import Pdb
from types import FrameType
from typing import Any

from marimo import _loggers
from marimo._messaging.console_output_worker import _write_pdb_output
from marimo._messaging.streams import Stdin, Stdout
from marimo._runtime.context import ContextNotInitializedError, get_context

LOGGER = _loggers.marimo_logger()


class MarimoPdb(Pdb):
    def __init__(self, stdout: Stdout | None, stdin: Stdin | None):
        super().__init__(stdout=stdout, stdin=stdin)  # type: ignore[arg-type]
        LOGGER.debug("MarimoPdb.__init__")
        self.use_rawinput = stdin is None

    def set_trace(
        self, frame: FrameType | None = None, header: str | None = None
    ) -> None:
        try:
            ctx = get_context()
        except ContextNotInitializedError:
            LOGGER.warn("Context not initialized")
            return

        assert ctx.cell_id is not None
        _write_pdb_output(
            ctx.stream,
            ctx.cell_id,
            "start",
        )
        if header is not None:
            sys.stdout.write(header)
        return super().set_trace(frame)

    # TODO: break out of cmd loop when cell not executing
    # TODO: catch bdbquit somewhere
    def cmdloop(self, intro: Any | None = None) -> None:
        """Run the command loop until a `quit` command is issued."""
        try:
            ctx = get_context()
        except ContextNotInitializedError:
            LOGGER.warn("Context not initialized")
            return

        LOGGER.debug("cmdloop: %s", intro)
        try:
            return super().cmdloop(intro)
        finally:
            _write_pdb_output(
                ctx.stream,
                ctx.cell_id,
                "stop",
            )

            # Restore stdout after the debugger loop is finished
            ...
            # sys.stdout = self.original_stdout


def set_trace(
    debugger: MarimoPdb,
    frame: FrameType | None = None,
    header: str | None = None,
) -> None:
    debugger.set_trace(frame, header=header)
