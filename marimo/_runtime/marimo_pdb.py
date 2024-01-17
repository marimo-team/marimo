from __future__ import annotations

import sys
from pdb import Pdb
from types import FrameType

from marimo import _loggers
from marimo._messaging.console_output_worker import _write_pdb_output
from marimo._runtime.context import ContextNotInitializedError, get_context

LOGGER = _loggers.marimo_logger()


class MarimoPdb(Pdb):
    def __init__(self):
        super().__init__()
        LOGGER.debug("MarimoPdb.__init__")
        self.original_stdout = sys.stdout
        sys.stdout = self.stdout
        self.use_rawinput = False  # Do not read from stdin

    def _on_output(self, output: str) -> None:
        try:
            ctx = get_context()
        except ContextNotInitializedError:
            LOGGER.warn("Context not initialized")
            return

        if ctx.stdout:
            ctx.stdout.write("<marimo-pdb> ")
            ctx.stdout.write(output)

    def set_trace(self, frame: FrameType | None = None) -> None:
        try:
            ctx = get_context()
        except ContextNotInitializedError:
            LOGGER.warn("Context not initialized")
            return

        _write_pdb_output(
            None,
            ctx.cell_id,
            "start",
        )
        return super().set_trace(frame)

    def cmdloop(self, intro: str = None) -> None:
        """Run the command loop until a `quit` command is issued."""
        LOGGER.debug("cmdloop: %s", intro)
        try:
            return super().cmdloop(intro)
        finally:
            # Restore stdout after the debugger loop is finished
            sys.stdout = self.original_stdout

    def __del__(self) -> None:
        # Restore stdout when the debugger is deleted
        sys.stdout = self.original_stdout

    def handle_input(self, input_value: str) -> None:
        """Handle input from the frontend"""
        LOGGER.debug("handle_pdb_input: %s", input_value)
        self.onecmd(input_value)

        output: str = str(self.stdout.readlines())
        LOGGER.debug("handle_pdb_output: %s", output)
        self._on_output(output)

        self.stdout.truncate(0)
        self.stdout.seek(0)


pdb = MarimoPdb()


def patch_pdb_with_marimo() -> None:
    """Patch the Pdb instance with Marimo-specific functionality"""
    sys.modules["pdb"] = pdb
