# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import re
import sys
import traceback
from collections.abc import Container
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from marimo._ast.cell import CellId_t, execute_cell
from marimo._runtime import dataflow
from marimo._runtime.control_flow import MarimoInterrupt, MarimoStopError

if TYPE_CHECKING:
    from marimo._runtime.state import State


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
class RunResult:
    # Raw output of cell
    output: Any
    # Exception raised by cell, if any
    exception: Optional[Exception]

    def success(self) -> bool:
        """Whether the cell exected successfully"""
        return self.exception is None


class Runner:
    """Runner for a collection of cells."""

    def __init__(
        self,
        cell_ids: set[CellId_t],
        graph: dataflow.DirectedGraph,
        glbls: dict[Any, Any],
    ):
        self.graph = graph
        # runtime globals
        self.glbls = glbls
        # cells that the runner will run.
        self.cells_to_run = dataflow.topological_sort(graph, cell_ids)
        # map from a cell that was cancelled to its descendants that have
        # not yet run:
        self.cells_cancelled: dict[CellId_t, set[CellId_t]] = {}
        # whether the runner has been interrupted
        self.interrupted = False
        # mapping from cell_id to exception it raised
        self.exceptions: dict[CellId_t, Exception] = {}

        # each cell's position in the run queue
        self._run_position = {
            cell_id: index for index, cell_id in enumerate(self.cells_to_run)
        }

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

    def _get_run_position(self, cell_id: CellId_t) -> Optional[int]:
        """Position in the original run queue"""
        return (
            self._run_position[cell_id]
            if cell_id in self._run_position
            else None
        )

    def _runs_after(
        self, source: CellId_t, target: CellId_t
    ) -> Optional[bool]:
        """Compare run positions.

        Returns `True` if source runs after target, `False` if target runs
        after source, or `None` if not comparable
        """
        source_pos = self._get_run_position(source)
        target_pos = self._get_run_position(target)
        if source_pos is None or target_pos is None:
            return None
        return source_pos > target_pos

    def resolve_state_updates(
        self,
        state_updates: dict[State[Any], CellId_t],
        errored_cells: Container[CellId_t],
    ) -> set[CellId_t]:
        """
        Get cells that need to be run as a consequence of state updates

        A cell is marked as needing to run if all of the following are true:

            1. The runner was not interrupted.
            2. It was not already run after its setter was called.
            3. It isn't the cell that called the setter.
            4. It is not errored (unable to run) or cancelled.
            5. It has among its refs the state object whose setter
               was invoked.

        (3) means that a state update in a given cell will never re-trigger
        the same cell to run. This is similar to how interacting with
        a UI element in the cell that created it won't re-trigger the cell,
        and this behavior is useful when tieing UI elements together with a
        state object.

        **Arguments.**

        - state_updates: mapping from state object to the cell that last ran
          its setter
        - errored_cells: cell ids that are unable to run
        """
        # No updates when the runner is interrupted (condition 1)
        if self.interrupted:
            return set()

        cids_to_run: set[CellId_t] = set()
        for state, setter_cell_id in state_updates.items():
            for cid, cell in self.graph.cells.items():
                # Don't re-run cells that already ran with new state (2)
                if self._runs_after(source=cid, target=setter_cell_id):
                    continue
                # No self-loops (3)
                if cid == setter_cell_id:
                    continue
                # No errorred/cancelled cells (4)
                if cid in errored_cells or self.cancelled(cid):
                    continue
                # State object in refs (5)
                for ref in cell.refs:
                    # run this cell if any of its refs match the state object
                    # by object ID (via is operator)
                    if ref in self.glbls and self.glbls[ref] is state:
                        cids_to_run.add(cid)
        return cids_to_run

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
            # User interrupt
            # interrupt the entire runner
            self.interrupted = True
            run_result = RunResult(output=None, exception=e)
            self.print_traceback()
        except MarimoStopError as e:
            # Raised by mo.stop().
            # cancel only the descendants of this cell
            self.cancel(cell_id)
            run_result = RunResult(output=e.output, exception=e)
            # don't print a traceback, since quitting is the intended
            # behavior (like sys.exit())
        except Exception as e:  # noqa: E722
            # cancel only the descendants of this cell
            self.cancel(cell_id)
            run_result = RunResult(output=None, exception=e)
            self.print_traceback()

        if run_result.exception is not None:
            self.exceptions[cell_id] = run_result.exception

        return run_result
