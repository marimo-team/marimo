# Copyright 2026 Marimo. All rights reserved.
"""Snapshot of cell outputs delivered to the kernel for a scratchpad execution.

Sibling to :mod:`marimo._messaging.notebook.document`.  Kept separate
because :class:`NotebookDocument` is structural-only — cell ordering,
code, names, and configs — while outputs are *execution* state produced
by the kernel and aggregated on the session side.  Bundling outputs
onto the document would muddy that line; two parallel ContextVars keep
each layer's concerns crisp.

The snapshot is *frozen* at the start of a scratchpad invocation.  It
will not reflect outputs produced by ``ctx.run_cell`` calls in the same
batch — agents that need fresh outputs should re-enter
``cm.get_context()``.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

import msgspec

from marimo._messaging.cell_output import CellOutput
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Generator


class CellOutputs(msgspec.Struct):
    """Per-cell output snapshot delivered alongside the document snapshot.

    ``output`` carries the cell's last main (rich display) output;
    ``console_outputs`` carries the buffered stdout/stderr stream from
    its last execution.  Both are keyed by cell id; missing keys mean
    "no output captured" (the cell never ran, or produced nothing on
    that channel).
    """

    output: dict[CellId_t, CellOutput]
    console_outputs: dict[CellId_t, list[CellOutput]]


#: Output snapshot for the current scratchpad execution.  Set by the
#: kernel before running code_mode so ``AsyncCodeModeContext`` can read
#: cell outputs without the kernel keeping a live reference to the
#: session view.
_current_outputs: ContextVar[CellOutputs | None] = ContextVar(
    "_current_outputs", default=None
)


def get_current_outputs() -> CellOutputs | None:
    """Return the output snapshot for the current execution, if any."""
    return _current_outputs.get()


@contextmanager
def notebook_outputs_context(
    outputs: CellOutputs | None,
) -> Generator[None, None, None]:
    """Context manager for setting and resetting the current output snapshot."""
    token = _current_outputs.set(outputs)
    try:
        yield
    finally:
        _current_outputs.reset(token)
