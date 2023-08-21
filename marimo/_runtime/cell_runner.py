# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import io
import pprint
import re
import sys
import traceback
from dataclasses import dataclass
from typing import Any, Optional

from marimo._ast.cell import CellId_t, execute_cell
from marimo._output import formatting
from marimo._runtime import dataflow
from marimo._runtime.control_flow import MarimoInterrupt, MarimoStopError


def cell_filename(cell_id: CellId_t) -> str:
    """Filename to use when running cells through exec."""
    return f"<cell-{cell_id}>"


def cell_id_from_filename(filename: str) -> Optional[CellId_t]:
    """Parses cell id from filename."""
    matches = re.findall(r"<cell-([0-9]+)>", filename)
    if matches:
        return str(matches[0])
    return None


def format_traceback(graph: dataflow.DirectedGraph) -> str:
    """Formats the current exception on the stack."""
    # all three values are guaranteed to be non-None because an
    # exception is on the stack:
    # https://docs.python.org/3/library/sys.html#sys.exc_info
    exc_type, exc_value, tb = sys.exc_info()
    # custom traceback formatting strips out marimo internals
    # and adds source code from cells
    frames = traceback.extract_tb(tb)
    error_msg_lines = []
    found_cell_frame = False
    for filename, lineno, fn_name, text in frames:
        filename_cell_id = cell_id_from_filename(filename)
        in_cell = filename_cell_id is not None
        if in_cell:
            found_cell_frame = True
        if not found_cell_frame:
            continue

        line = "  "
        if in_cell:
            # TODO: hyperlink to cell ... should the traceback
            # be assembled in the frontend?
            line += f"Cell {filename}, "
        else:
            line += f"File {filename}, "
        line += f"line {lineno}"

        if fn_name != "<module>":
            line += f", in {fn_name}"
        error_msg_lines.append(line)

        if filename_cell_id is not None:
            lines = graph.cells[filename_cell_id].code.split("\n")
            error_msg_lines.append("    " + lines[lineno - 1].strip())
        else:
            error_msg_lines.append("    " + text.strip())

    return (
        "Traceback (most recent call last):\n"
        + "\n".join(error_msg_lines)
        + "\n"
        + exc_type.__name__  # type: ignore
        + ": "
        + str(exc_value)
    )


@dataclass
class FormattedOutput:
    """Cell output transformed to wire format."""

    channel: str
    mimetype: str
    data: str
    # non-None if there was an error in formatting the cell output.
    traceback: Optional[str] = None


@dataclass
class RunResult:
    # Raw output of cell
    output: Any
    # Exception raised by cell, if any
    exception: Optional[Exception]

    def success(self) -> bool:
        """Whether the cell exected successfully"""
        return self.exception is None

    def format_output(self) -> FormattedOutput:
        """Formats raw output to wire format."""
        return_value = "" if self.output is None else self.output
        if (formatter := formatting.get_formatter(return_value)) is not None:
            try:
                mimetype, data = formatter(return_value)
                return FormattedOutput(
                    channel="output", mimetype=mimetype, data=data
                )
            except Exception:  # noqa: E722
                return FormattedOutput(
                    channel="output",
                    mimetype="text/plain",
                    data="",
                    traceback=traceback.format_exc(),
                )
        else:
            tmpio = io.StringIO()
            tb = None
            if isinstance(return_value, str):
                tmpio.write(return_value)
            else:
                try:
                    pprint.pprint(return_value, stream=tmpio)
                except Exception:  # noqa: E722
                    tmpio.write("")
                    tb = traceback.format_exc()
            tmpio.seek(0)
            return FormattedOutput(
                channel="output",
                mimetype="text/plain",
                data=tmpio.read(),
                traceback=tb,
            )


class Runner:
    """Runner for a collection of cells."""

    def __init__(
        self,
        cell_ids: set[CellId_t],
        graph: dataflow.DirectedGraph,
        glbls: dict[Any, Any],
    ):
        self.graph = graph
        self.glbls = glbls
        self.cells_to_run = dataflow.topological_sort(graph, cell_ids)
        self.cells_cancelled: dict[CellId_t, set[CellId_t]] = {}
        self.interrupted = False
        self.exceptions: dict[CellId_t, Exception] = {}

    def cancel(self, cell_id: CellId_t) -> None:
        """Mark a cell (and its descendants) as cancelled."""
        self.cells_cancelled[cell_id] = set(
            cid
            for cid in dataflow.transitive_closure(self.graph, set([cell_id]))
            if cid in self.cells_to_run
        )

    def cancelled(self, cell_id: CellId_t) -> bool:
        """Return whether a cell has been cancelled."""
        return any(
            cell_id in cancelled for cancelled in self.cells_cancelled.values()
        )

    def pending(self) -> bool:
        """Whether there are more cells to run."""
        return not self.interrupted and len(self.cells_to_run) > 0

    def pop_cell(self) -> CellId_t:
        """Get the next cell to run."""
        return self.cells_to_run.pop(0)

    def print_traceback(self) -> None:
        """Print a traceback to stderr.

        Must be called when there is an exception on the stack.
        """
        error_msg = format_traceback(self.graph)
        sys.stderr.write(error_msg)

    def run(self, cell_id: CellId_t) -> RunResult:
        """Run a cell."""
        cell = self.graph.cells[cell_id]
        try:
            return_value = execute_cell(cell, self.glbls)
            run_result = RunResult(output=return_value, exception=None)
        except MarimoInterrupt as e:
            # interrupt the entire runner
            self.interrupted = True
            run_result = RunResult(output=None, exception=e)
            self.print_traceback()
        except MarimoStopError as e:
            # cancel only the descendants of this cell
            self.cancel(cell_id)
            run_result = RunResult(output=e.output, exception=e)
            self.print_traceback()
        except Exception as e:  # noqa: E722
            # cancel only the descendants of this cell
            self.cancel(cell_id)
            run_result = RunResult(output=None, exception=e)
            self.print_traceback()

        if run_result.exception is not None:
            self.exceptions[cell_id] = run_result.exception

        return run_result
