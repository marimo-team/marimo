# Copyright 2026 Marimo. All rights reserved.
"""AsyncCodeModeContext: programmatic notebook editing via async context manager.

.. warning::

    **Internal, agent-only API.** Not part of marimo's public API.
    No versioning guarantees. May change or be removed without notice.

Usage::

    import marimo._code_mode as cm

    async with cm.get_context() as ctx:
        cid = ctx.create_cell("x = 1")
        cid2 = ctx.create_cell("y = x + 1", after=cid)
        ctx.edit_cell("my_cell", code="z = 42")
        ctx.delete_cell("old_cell")
        ctx.move_cell("my_cell", after="other_cell")
        ctx.run_cell(cid)
        ctx.run_cell(cid2)
        ctx.run_cell("my_cell")
"""

from __future__ import annotations

import asyncio
import keyword
import sys
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast, overload
from uuid import uuid4

from msgspec.structs import replace as structs_replace

from marimo import _loggers
from marimo._ast.cell import (
    CellConfig,
    CellImpl,
    RunResultStatusType,
    RuntimeStateType,
)
from marimo._ast.cell_id import CellIdGenerator
from marimo._ast.compiler import compile_cell
from marimo._ast.names import SETUP_CELL_NAME, is_internal_cell_name
from marimo._code_mode._better_inspect import _HelpableEnumMeta, helpable
from marimo._code_mode._packages import (
    PackageResult,
    Packages,
    _AddPackage,
)
from marimo._code_mode._plan import (
    _AddOp,
    _build_plan,
    _DeleteOp,
    _document_changes,
    _MoveOp,
    _Op,
    _PlanEntry,
    _UpdateOp,
    _validate_ops,
)
from marimo._code_mode.screenshot_meta import (
    SCREENSHOT_AUTH_TOKEN_KEY,
    SCREENSHOT_FILE_KEY,
    SCREENSHOT_SERVER_URL_KEY,
)
from marimo._core import protocol
from marimo._core.document import Document, DocumentCell
from marimo._messaging.cell_output import CellOutput
from marimo._messaging.errors import Error
from marimo._messaging.host import DocumentRequest, runtime_config
from marimo._messaging.notebook.outputs import (
    CellOutputs,
    get_current_outputs,
)
from marimo._messaging.notification import (
    Notification,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.commands import (
    CommandMessage,
    DocumentReplyCommand,
    UpdateUIElementCommand,
)
from marimo._runtime.context import (
    get_context as _get_runtime_context,
    safe_get_context,
)
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.dataflow import DirectedGraph
from marimo._runtime.scratch import get_current_document
from marimo._types.ids import CellId_t, UIElementId
from marimo._utils.formatter import DefaultFormatter

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence
    from os import PathLike
    from types import TracebackType
    from typing import Self

    from marimo._ast.cell_manager import CellManager
    from marimo._code_mode.screenshot import _ScreenshotSession
    from marimo._runtime.runtime import Kernel


def _validate_cell_name(name: str | None) -> None:
    if name is None or name == "":
        return
    if is_internal_cell_name(name):
        raise ValueError(
            f"Invalid cell name {name!r}. {name!r} is reserved for unnamed "
            "cells."
        )
    if unicodedata.normalize("NFKC", name) != name:
        raise ValueError(
            f"Invalid cell name {name!r}. Cell names must be NFKC-normalized."
        )
    if not name.isidentifier() or keyword.iskeyword(name):
        raise ValueError(
            f"Invalid cell name {name!r}. Cell names must be valid, "
            "non-keyword Python identifiers, such as 'load_data' or "
            "'analysis_summary'."
        )


@helpable
class CellStatusType(str, Enum, metaclass=_HelpableEnumMeta):
    """Synthesized cell execution status.

    Returned by `NotebookCell.status`.  Compares equal to plain
    strings, so `cell.status == "idle"` works as expected.
    """

    idle = "idle"
    """Ran successfully, up to date."""
    exception = "exception"
    """Cell raised an exception."""
    stale = "stale"
    """Needs re-run (code edited, inputs changed, or never run)."""
    cancelled = "cancelled"
    """Ancestor raised an exception."""
    interrupted = "interrupted"
    """Execution was interrupted."""
    marimo_error = "marimo-error"
    """Prevented from executing (e.g. multiply-defined name)."""
    disabled = "disabled"
    """Cell is disabled."""
    queued = "queued"
    """Waiting to run."""
    running = "running"
    """Currently executing."""

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return repr(self.value)


CellErrorKind = Literal["graph", "runtime"]


@helpable
@dataclass(frozen=True, slots=True)
class CellError:
    """An error affecting a notebook cell.

    Parameters
    ----------
    kind : `"graph"` or `"runtime"`
        `"graph"` — a dataflow-graph error that *prevents* execution
        (multiply-defined variable, cycle, etc.).
        `"runtime"` — an exception raised during execution.
    msg : str
        Human-readable description.
    exception : Exception | None
        The original `Exception` for runtime errors; `None` for
        graph errors.
    """

    kind: CellErrorKind
    msg: str
    exception: Exception | None = None

    def __repr__(self) -> str:
        return f"CellError(kind={self.kind!r}, msg={self.msg!r})"


class CellRuntimeState(Protocol):
    """The subset of `CellImpl` that `NotebookCell` reads."""

    @property
    def code(self) -> str: ...
    @property
    def runtime_state(self) -> RuntimeStateType | None: ...
    @property
    def run_result_status(self) -> RunResultStatusType | None: ...
    @property
    def stale(self) -> bool: ...
    @property
    def exception(self) -> Exception | None: ...


LOGGER = _loggers.marimo_logger()

# Set the first time `ctx.install_packages` (legacy alias) is used in a
# session, so the nudge is printed once per process instead of every call.
_LEGACY_INSTALL_WARNED = False


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def get_context(
    *,
    skip_validation: bool = False,
    skip_staleness_check: bool = False,
) -> AsyncCodeModeContext:
    """Return an `AsyncCodeModeContext` for the running kernel.

    Use as an async context manager::

        async with cm.get_context() as ctx:
            ctx.create_cell("x = 1")

    Parameters
    ----------
    skip_validation : bool, default False
        When False (the default), a dry-run compile check runs on exit
        to catch syntax errors, multiply-defined names, and cycles
        *before* any graph mutations are applied. The check is cheap
        and should almost never be disabled. Only set to True when you
        intentionally need to insert code that would fail validation
        (e.g. incomplete stubs the user plans to fix by hand).
    skip_staleness_check : bool, default False
        When False (the default), `edit_cell` raises
        :class:`StaleCellError` if the agent tries to overwrite a cell
        whose code has changed since the agent last read it (e.g. via
        `ctx.cells[cell_id].code`). Set to True to overwrite blindly —
        useful when the agent intentionally discards prior content.
    """
    runtime_ctx = _get_runtime_context()
    if not isinstance(runtime_ctx, KernelRuntimeContext):
        raise RuntimeError("code mode requires a running kernel context")
    if sys.platform == "emscripten" or runtime_ctx.active_scheduler is None:
        raise RuntimeError("Code mode requires a native agent scratchpad")
    cell_manager = runtime_ctx._app.cell_manager if runtime_ctx._app else None
    return AsyncCodeModeContext(
        runtime_ctx._kernel,
        cell_manager=cell_manager,
        skip_validation=skip_validation,
        skip_staleness_check=skip_staleness_check,
    )


class StaleCellError(RuntimeError):
    """Raised when `edit_cell` targets a cell the agent has not read at
    its current version.

    `stale_cells` is the full set of cells in the same boat, so the agent
    can re-read all of them in one pass.
    """

    def __init__(
        self,
        cell_id: CellId_t,
        stale_cells: frozenset[CellId_t],
    ) -> None:
        self.cell_id = cell_id
        self.stale_cells = stale_cells
        others = sorted(stale_cells - {cell_id})
        other_hint = (
            f"\nOther stale cells: {', '.join(others)}." if others else ""
        )
        super().__init__(
            f"Cell {cell_id!r} was modified since the agent last read it.\n"
            f"Read it first (e.g. `ctx.cells[{cell_id!r}].code`) before "
            f"editing.{other_hint}\n"
            f"To override and overwrite without re-reading, pass "
            f"skip_staleness_check=True to cm.get_context()."
        )


@helpable
class NotebookCell:
    """Read-only view of a single cell with runtime status.

    Wraps the document-level cell data and enriches it with
    live execution state from the kernel's dependency graph.

    Properties
    ----------
    id : CellId_t
    code : str
    name : str
    config : CellConfig
    status : CellStatusType | None
        Synthesized execution status. Priority order:
        transient state (queued/running/disabled) > stale > last run result.
        `None` if the cell has never been registered in the graph.
    errors : list[CellError]
        Structured errors affecting this cell.
        Each entry is a `CellError` with `kind`, `msg`, and
        `exception` fields. Covers both runtime exceptions
        (e.g. `NameError`) and graph errors (multiply-defined
        variables, cycles, etc.).
    output : CellOutput | None
        The cell's last main (rich display) output, or `None` if no
        output was captured. **Frozen snapshot** — taken at
        scratchpad-start, not refreshed when `ctx.run_cell` produces
        new outputs in the same batch. Start a new code-mode invocation
        to see fresh outputs.
    console_outputs : list[CellOutput]
        Buffered stdout/stderr outputs from the cell's last execution.
        Same frozen-snapshot caveat as `output`.
    """

    __slots__ = (
        "_cell",
        "_graph_errors",
        "_impl",
        "_outputs",
        "_record_read",
    )

    def __init__(
        self,
        cell: DocumentCell,
        cell_impl: CellRuntimeState | None,
        graph_errors: tuple[Error, ...] = (),
        outputs: CellOutputs | None = None,
        record_read: Callable[[], None] | None = None,
    ) -> None:
        self._cell = cell
        self._impl = cell_impl
        self._graph_errors = graph_errors
        self._outputs = outputs
        self._record_read = record_read

    # -- document properties (delegated) --

    @property
    def id(self) -> CellId_t:
        """The unique cell identifier."""
        return CellId_t(self._cell.id)

    @property
    def code(self) -> str:
        """The current source code of the cell."""
        if self._record_read is not None:
            self._record_read()
        return self._cell.code

    @property
    def name(self) -> str:
        """The cell's display name (empty string if unnamed)."""
        return self._cell.name

    @property
    def config(self) -> CellConfig:
        """The cell's configuration (e.g. disabled, hide_code)."""
        return runtime_config(self._cell.config)

    # -- runtime properties --

    def _is_stale(self) -> bool:
        """Whether the cell needs to be (re-)run.

        True when:
        - The cell has code but was never run (no impl in the graph).
        - The cell's code was edited since it was last run.
        - The runtime marked the cell stale (lazy mode: inputs changed).
        """
        if self._impl is None:
            return bool(self._cell.code)
        return self._cell.code != self._impl.code or self._impl.stale

    @property
    def status(self) -> CellStatusType | None:
        """Synthesized cell status.

        Possible values:

        - `"idle"` — ran successfully, up to date.
        - `"exception"` — cell raised an exception.
        - `"stale"` — needs re-run (code edited, inputs changed, or never run).
        - `"cancelled"` — ancestor raised an exception.
        - `"interrupted"` — execution was interrupted.
        - `"marimo-error"` — prevented from executing (e.g. multiply-defined name).
        - `"disabled"` — cell is disabled.
        - `"queued"` — waiting to run.
        - `"running"` — currently executing.
        - `None` — empty cell, never registered in the graph.

        Priority: transient state (queued/running/disabled) >
        stale > last run result.
        """
        if self._impl is None:
            return CellStatusType.stale if self._cell.code else None
        # Transient runtime state takes priority.
        rs = self._impl.runtime_state
        if rs == "queued":
            return CellStatusType.queued
        if rs == "running":
            return CellStatusType.running
        if rs == "disabled-transitively":
            return CellStatusType.disabled
        # Stale overrides last run result.
        if self._is_stale():
            return CellStatusType.stale
        # Fall back to last execution result.
        rr = self._impl.run_result_status
        if rr is None:
            # Registered in the graph but never executed.
            return CellStatusType.stale if self._cell.code else None
        if rr == "success":
            return CellStatusType.idle
        return CellStatusType(rr)

    @property
    def errors(self) -> list[CellError]:
        """All errors affecting this cell.

        Returns a list of :class:`CellError` objects. Each has a
        `kind` (`"graph"` or `"runtime"`), a human-readable
        `msg`, and for runtime errors the original `exception`.

        Returns an empty list when the cell is healthy.
        """
        result: list[CellError] = [
            CellError(kind="graph", msg=err.describe())
            for err in self._graph_errors
        ]
        if self._impl and self._impl.exception is not None:
            exc = self._impl.exception
            result.append(
                CellError(
                    kind="runtime",
                    msg=f"{type(exc).__name__}: {exc}",
                    exception=exc,
                )
            )
        return result

    @property
    def output(self) -> CellOutput | None:
        """The cell's last main (rich display) output, or `None`.

        Frozen at scratchpad-start — does not reflect outputs produced
        by `ctx.run_cell` in the same batch. Start a new code-mode
        invocation to see fresh outputs.
        """
        if self._outputs is None:
            return None
        return self._outputs.output.get(self.id)

    @property
    def console_outputs(self) -> list[CellOutput]:
        """Buffered stdout/stderr outputs from the last execution.

        Returns an empty list when no console output was captured.
        Same frozen-snapshot semantics as `output`.
        """
        if self._outputs is None:
            return []
        return list(self._outputs.console_outputs.get(self.id, ()))

    # -- display --

    def __repr__(self) -> str:
        first_line = self.code.split("\n", 1)[0]
        if len(first_line) > 80:
            code_preview = first_line[:80] + "..."
        elif "\n" in self.code:
            code_preview = first_line + "..."
        else:
            code_preview = first_line
        name_part = f", name={self.name!r}" if self.name else ""
        status_part = f", status={self.status!r}" if self.status else ""
        errors = self.errors
        errors_part = f", errors={errors!r}" if errors else ""
        return (
            f"NotebookCell(id={self.id!r}{name_part}"
            f"{status_part}{errors_part}, code={code_preview!r})"
        )


@helpable
class _CellsView:
    """Read-only, ordered view over notebook cells.

    Supports lookup by integer index, cell ID, or cell name::

        ctx.cells[0]  # by index
        ctx.cells[-1]  # negative index
        ctx.cells["Abcd1234"]  # by cell ID
        ctx.cells["my_cell"]  # by cell name

    Iteration yields `NotebookCell` objects with runtime status::

        for cell in ctx.cells:
            print(cell.id, cell.code, cell.status)

    Dict-like access is also available::

        ctx.cells.keys()  # list of CellId_t
        ctx.cells.values()  # sequence of NotebookCell
        ctx.cells.items()  # sequence of (CellId_t, NotebookCell)
        "my_cell" in ctx.cells  # membership test
    """

    def __init__(self, ctx: AsyncCodeModeContext) -> None:
        self._ctx = ctx

    @property
    def _doc(self) -> Document:
        return (
            self._ctx._document
            if self._ctx._entered
            else self._ctx._scratch_document.document
        )

    def _cell_view(self, cell: DocumentCell) -> NotebookCell:
        """Wrap a document cell with runtime state from the graph."""
        try:
            graph = self._ctx.graph
            impl = graph.cells.get(CellId_t(cell.id))
            graph_errors = self._ctx._kernel.errors.get(CellId_t(cell.id), ())
            outputs = self._ctx._outputs
        except AttributeError:
            impl = None
            graph_errors = ()
            outputs = None

        def record_read() -> None:
            self._ctx._kernel.agent.read_etags[CellId_t(cell.id)] = cell.etag

        return NotebookCell(
            cell,
            impl,
            graph_errors=graph_errors,
            outputs=outputs,
            record_read=record_read,
        )

    def _cell_ids(self) -> list[CellId_t]:
        return [CellId_t(cell.id) for cell in self._doc]

    def _cell_name(self, cell_id: CellId_t) -> str | None:
        doc_cell = self._doc.cell(protocol.CellId(cell_id))
        if doc_cell is None:
            return None
        return doc_cell.name or None

    def _resolve(self, target: str) -> CellId_t:
        """Resolve a cell ID or cell name to a `CellId_t`.

        Raises `KeyError` if not found.
        """
        if self._doc.cell(protocol.CellId(target)) is not None:
            return CellId_t(target)

        # Fall back to cell name.
        for cell in self._doc:
            if cell.name == target:
                return CellId_t(cell.id)

        available = ", ".join(c.id for c in self._doc)
        raise KeyError(
            f"Cell {target!r} not found. "
            f"Available cell IDs: [{available}]. "
            f"IDs are stable across reorders — re-read ctx.cells "
            f"if the notebook structure changed."
        )

    def __len__(self) -> int:
        return len(list(self._doc))

    @overload
    def __getitem__(self, key: int) -> NotebookCell: ...
    @overload
    def __getitem__(self, key: str) -> NotebookCell: ...

    def __getitem__(self, key: int | str) -> NotebookCell:
        if isinstance(key, int):
            return self._cell_view(list(self._doc)[key])
        cell = self._doc.cell(protocol.CellId(self._resolve(key)))
        assert cell is not None
        return self._cell_view(cell)

    def __iter__(self) -> Iterator[NotebookCell]:
        for cell in self._doc:
            yield self._cell_view(cell)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, int):
            return 0 <= key < len(self)
        if isinstance(key, str):
            try:
                self._resolve(key)
                return True
            except KeyError:
                return False
        return False

    def keys(self) -> Sequence[CellId_t]:
        """Return cell IDs in notebook order."""
        return self._cell_ids()

    def values(self) -> Sequence[NotebookCell]:
        """Return cell data in notebook order."""
        return [self._cell_view(c) for c in self._doc]

    def items(self) -> Sequence[tuple[CellId_t, NotebookCell]]:
        """Return (cell_id, cell_data) pairs in notebook order."""
        return [(CellId_t(c.id), self._cell_view(c)) for c in self._doc]

    # ------------------------------------------------------------------
    # Content search
    # ------------------------------------------------------------------

    def find(self, substring: str) -> Sequence[NotebookCell]:
        """Return cells whose code contains *substring*.

        Performs a case-sensitive substring search on each cell's code.

        Example::

            ctx.cells.find("import marimo")
        """
        return [self._cell_view(c) for c in self._doc if substring in c.code]

    def grep(self, pattern: str) -> Sequence[NotebookCell]:
        r"""Return cells whose code matches the regex *pattern*.

        Uses :func:`re.search` so the pattern can match anywhere in
        the cell's code.

        Example::

            ctx.cells.grep(r"alt\.Chart")
        """
        import re

        compiled = re.compile(pattern)
        return [
            self._cell_view(c) for c in self._doc if compiled.search(c.code)
        ]

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        doc_cells = list(self._doc)
        n = len(doc_cells)
        max_shown = 10
        lines = [f"CellsView({n} cell{'s' if n != 1 else ''}):"]

        def _fmt(i: int, c: DocumentCell) -> str:
            cv = self._cell_view(c)
            # Read through the wrapper so the staleness tracker sees
            # the preview as a read of the cell's source.
            first_line = cv.code.split("\n", 1)[0]
            code_preview = first_line[:50]
            if len(first_line) > 50:
                code_preview += "..."
            name_part = f" ({c.name})" if c.name else ""
            status_part = f" [{cv.status}]" if cv.status else ""
            return f"  [{i}] {c.id}{name_part}{status_part} | {code_preview}"

        if n <= max_shown:
            for i, c in enumerate(doc_cells):
                lines.append(_fmt(i, c))
        else:
            for i, c in enumerate(doc_cells[:max_shown]):
                lines.append(_fmt(i, c))
            omitted = n - max_shown - 1
            if omitted > 0:
                lines.append(
                    f"  ... {omitted} more cell"
                    f"{'s' if omitted != 1 else ''} ..."
                )
            lines.append(_fmt(n - 1, doc_cells[-1]))
        return "\n".join(lines)


# ------------------------------------------------------------------
# Context
# ------------------------------------------------------------------


@helpable
class AsyncCodeModeContext:
    """Async programmatic control of a running marimo notebook.

    Use as an async context manager. Cell edits are queued during the
    block and submitted together on exit. Requested runs finish before
    the context returns; a failed run does not roll back accepted edits::

        async with cm.get_context() as ctx:
            ctx.create_cell("x = 1")
            ctx.edit_cell("my_cell", code="x = 42")
            ctx.delete_cell("old_cell")

    Pending notebook updates can reject cell edits and requested cell runs.
    Requested runs require external updates to finish; edit-only batches
    may proceed on unrelated cells.
    Retry in a new agent execution so the kernel can process those updates.

    Read cells via `ctx.cells[key]` where *key* is an integer index,
    cell ID string, or cell name.
    """

    def __init__(
        self,
        kernel: Kernel,
        cell_manager: CellManager | None = None,
        *,
        skip_validation: bool = False,
        skip_staleness_check: bool = False,
    ) -> None:
        document = get_current_document()
        if document is None:
            raise RuntimeError(
                "NotebookDocument not available — code_mode requires "
                "a scratchpad execution with a notebook document"
            )
        self._kernel = kernel
        self._document = document.document
        self._scratch_document = document
        runtime = safe_get_context()
        self._scheduler = (
            runtime.active_scheduler
            if isinstance(runtime, KernelRuntimeContext)
            else None
        )
        try:
            self._owner_task = asyncio.current_task()
        except RuntimeError:
            self._owner_task = None
        # Output snapshot is optional — callers that don't pass one
        # (e.g. the MCP code server) get `cell.output is None` and
        # `cell.console_outputs == []` for every cell, same as cells
        # that genuinely produced no output.
        self._outputs: CellOutputs | None = get_current_outputs()
        self._cell_manager = cell_manager
        self._skip_validation = skip_validation
        self._skip_staleness_check = skip_staleness_check
        self._ops: list[_Op] = []
        # Track cell IDs added during this batch so subsequent ops
        # can reference them before they exist in the graph.
        self._pending_adds: dict[CellId_t, _AddOp] = {}
        # ID generator for new cells — seed=None uses OS entropy so we
        # never replay a prior session's ID sequence.  seen_ids from the
        # document prevents collisions with cells already on disk.
        self._id_generator = CellIdGenerator(seed=None)
        self._id_generator.seen_ids = {
            CellId_t(cell.id) for cell in document.document
        }
        self._packages = Packages(self)
        self._ui_updates: list[tuple[UIElementId, Any]] = []
        self._cells_to_run: set[CellId_t] = set()
        self._entered = False
        self._screenshot_session: _ScreenshotSession | None = None

    def _require_entered(self) -> None:
        if not self._entered:
            raise RuntimeError(
                "Cell operations require 'async with'. Use:\n"
                "\n"
                "    async with cm.get_context() as ctx:\n"
                "        ctx.create_cell(...)\n"
                "\n"
                "Without 'async with', operations are silently lost."
            )

    def __getattr__(self, name: str) -> Any:
        # Legacy alias: `ctx.install_packages(...)` was the pre-namespace
        # API. Kept as a hidden shim for in-flight skills / examples;
        # does not appear in dir() or IDE completion. Prefer
        # `ctx.packages.add(...)` in new code.
        if name == "install_packages":
            global _LEGACY_INSTALL_WARNED
            if not _LEGACY_INSTALL_WARNED:
                _LEGACY_INSTALL_WARNED = True
                sys.stderr.write(
                    "note: ctx.install_packages() is a legacy alias — "
                    "please update to ctx.packages.add()\n"
                )
            return self.packages.add
        raise AttributeError(
            f"{type(self).__name__!r} object has no attribute {name!r}"
        )

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    def _require_owner(self) -> None:
        task = asyncio.current_task()
        if (
            self._owner_task is not None
            and self._owner_task is not task
            or self._scheduler is not None
            and not self._scheduler.owns_task(task)
        ):
            raise RuntimeError(
                "Code mode must flush in the task that created its context"
            )

    async def __aenter__(self) -> Self:
        self._require_owner()
        self._ops = []
        self._pending_adds = {}
        self._packages._reset()
        self._ui_updates = []
        self._cells_to_run = set()
        await self._request_document()
        self._entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._require_owner()
        self._entered = False
        ops = self._ops
        ui_updates = self._ui_updates
        cells_to_run = self._cells_to_run
        self._ops = []
        self._pending_adds = {}
        self._ui_updates = []
        self._cells_to_run = set()

        await self.close_screenshot_session()

        if exc_type is not None:
            self._packages._reset()
            return  # let exception propagate, discard queued ops

        # Flush queued package ops before cell ops so newly added
        # cells can import newly installed packages.
        package_ops = await self._packages._flush()

        await self._flush_document(ops, cells_to_run)

        # Flush queued UI updates as a single batch.
        if ui_updates:
            object_ids, values = zip(*ui_updates, strict=False)
            await self._kernel.set_ui_element_value(
                UpdateUIElementCommand(
                    object_ids=list(object_ids),
                    values=list(values),
                ),
                notify_frontend=True,
            )

        # Print a summary of what was applied.
        self._print_summary(ops, package_ops, ui_updates, cells_to_run)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _print_summary(
        self,
        ops: list[_Op],
        package_ops: list[PackageResult],
        ui_updates: list[tuple[UIElementId, Any]],
        cells_to_run: set[CellId_t] | None = None,
    ) -> None:
        """Print a human-readable summary of applied operations."""
        lines: list[str] = []

        for result in package_ops:
            pkg_op = result.op
            if result.outcome == "restart-required":
                lines.append(
                    f"changes saved for {pkg_op.package}; restart the kernel to use them"
                )
                continue
            if result.outcome == "failed":
                action = (
                    "install"
                    if isinstance(pkg_op, _AddPackage)
                    else "uninstall"
                )
                lines.append(f"failed to {action} {pkg_op.package}")
                continue
            if isinstance(pkg_op, _AddPackage):
                lines.append(f"installed {pkg_op.package}")
            else:
                lines.append(f"uninstalled {pkg_op.package}")

        _run = cells_to_run or set()
        op_cell_ids: set[CellId_t] = set()
        for op in ops:
            cell_id = op.cell_id
            op_cell_ids.add(cell_id)
            label = self._cell_label(cell_id)
            ran = cell_id in _run
            errored = ran and self._cell_errored(cell_id)
            if isinstance(op, _AddOp):
                if errored:
                    verb = "created and ran"
                    suffix = " (error)"
                elif ran:
                    verb = "created and ran"
                    suffix = ""
                else:
                    verb = "created"
                    suffix = ""
                lines.append(f"{verb} cell {label}{suffix}")
            elif isinstance(op, _UpdateOp):
                parts = []
                if op.code is not None:
                    parts.append("code")
                if op.config is not None:
                    parts.append("config")
                detail = " and ".join(parts) if parts else "config"
                if errored:
                    suffix = " and ran (error)"
                elif ran:
                    suffix = " and ran"
                else:
                    suffix = ""
                lines.append(f"edited {detail} of cell {label}{suffix}")
            elif isinstance(op, _DeleteOp):
                lines.append(f"deleted cell {label}")
            elif isinstance(op, _MoveOp):
                lines.append(f"moved cell {label}")

        # Report cells queued for execution that had no structural op.
        if _run:
            for cell_id in _run:
                if cell_id not in op_cell_ids:
                    label = self._cell_label(cell_id)
                    errored = self._cell_errored(cell_id)
                    suffix = " (error)" if errored else ""
                    lines.append(f"re-ran cell {label}{suffix}")

        if ui_updates:
            lines.append(f"updated {len(ui_updates)} UI element(s)")

        if not lines:
            return

        # Add a blank line before the summary when cells errored,
        # so the summary is visually separated from streamed tracebacks.
        has_errors = _run and any(self._cell_errored(cid) for cid in _run)
        if has_errors:
            sys.stdout.write("\n")
        for line in lines:
            sys.stdout.write(line + "\n")

    def _cell_errored(self, cell_id: CellId_t) -> bool:
        """Return True if the cell raised an exception."""
        cell = self.graph.cells.get(cell_id)
        return cell is not None and cell.exception is not None

    def _cell_label(self, cell_id: CellId_t) -> str:
        """Return a display label: `'id' (name)` or `'id'`."""
        short = repr(str(cell_id)[:8])
        doc_cell = self._document.cell(protocol.CellId(cell_id))
        if doc_cell and doc_cell.name:
            return f"{short} ({doc_cell.name})"
        return short

    # ------------------------------------------------------------------
    # Read-only attributes
    # ------------------------------------------------------------------

    @property
    def graph(self) -> DirectedGraph:
        """The notebook's dependency graph."""
        return self._kernel.graph

    @property
    def globals(self) -> dict[str, Any]:
        """The kernel's global namespace (all variables defined by cells).

        Mutations via :meth:`run_cell` update the kernel globals but
        *not* the scratchpad's copy. Read values through this property
        (`ctx.globals["x"]`) rather than bare variable names.
        """
        return self._kernel.globals

    @property
    def cells(self) -> _CellsView:
        """Read-only view of notebook cells.

        Supports lookup by index, cell ID, or cell name::

            ctx.cells[0]  # by index
            ctx.cells["cell-id"]  # by cell ID
            ctx.cells["my_cell"]  # by cell name
        """
        return _CellsView(self)

    @property
    def packages(self) -> Packages:
        """Package management for the notebook's Python environment.

        List currently installed packages::

            ctx.packages.list()  # -> list[PackageDescription]

        Queue packages to install or remove; mutations flush on exit
        before cell ops so newly added cells can import them::

            ctx.packages.add("pandas", "numpy>=1.26")
            ctx.packages.remove("old-pkg")
        """
        return self._packages

    # ------------------------------------------------------------------
    # Mutation methods (queue ops, applied on __aexit__)
    # ------------------------------------------------------------------

    def _resolve_target(self, target: str) -> CellId_t:
        """Resolve a cell ID or name to a `CellId_t`.

        Checks the live graph first, then pending adds (by ID and by
        name), then queued renames from `edit_cell`.
        """
        # Try the live graph.
        try:
            return self.cells._resolve(target)
        except KeyError:
            pass

        # Try pending adds (by cell ID).
        cid = CellId_t(target)
        if cid in self._pending_adds:
            return cid

        # Try pending adds (by name).
        for pending_id, add_op in self._pending_adds.items():
            if add_op.name == target:
                return pending_id

        # Try queued renames from edit_cell ops.
        for op in self._ops:
            if isinstance(op, _UpdateOp) and op.name == target:
                return op.new_cell_id or op.cell_id

        raise KeyError(
            f"Cell {target!r} not found in notebook or pending adds"
        )

    def _resolve_new_cell(
        self, name: str | None
    ) -> tuple[CellId_t, str | None]:
        """Return `(cell_id, resolved_name)` for a new cell.

        The `"setup"` name is special-cased to use the well-known setup
        cell ID. Raises `ValueError` if a setup cell already exists.
        """
        if name == SETUP_CELL_NAME:
            # Check if a setup cell already exists (by name or by ID).
            try:
                self.cells._resolve(SETUP_CELL_NAME)
                raise ValueError(
                    "A setup cell already exists. Use "
                    'ctx.edit_cell("setup", code=...) to modify it.'
                )
            except KeyError:
                pass
            cell_id = (
                self._cell_manager.setup_cell_id
                if self._cell_manager is not None
                else CellId_t(SETUP_CELL_NAME)
            )
            return cell_id, SETUP_CELL_NAME
        cell_id = self._id_generator.create_cell_id()
        return cell_id, name

    def create_cell(
        self,
        code: str,
        *,
        before: str | None = None,
        after: str | None = None,
        hide_code: bool = True,
        disabled: bool = False,
        expand_output: bool = False,
        column: int | None = None,
        name: str | None = None,
    ) -> CellId_t:
        """Queue a new cell. Returns the new cell's ID.

        The returned ID can be used in subsequent operations within the
        same batch (e.g. as an `after` target for the next cell).

        Cells are not executed automatically. Use `run_cell` to queue
        them for execution::

            cid = ctx.create_cell("x = 1")
            ctx.run_cell(cid)

        Examples:
            ```python
            # Append at the end
            cid = ctx.create_cell("import pandas as pd")

            # Chain cells in order
            cid2 = ctx.create_cell("df = pd.read_csv('data.csv')", after=cid)
            ctx.create_cell("df.head()", after=cid2)

            # Create and run
            cid = ctx.create_cell("x = 1")
            ctx.run_cell(cid)
            ```

        Args:
            code (str): Python source code for the cell.
            before (str, optional): Insert before this cell (ID or name).
                Mutually exclusive with `after`.
            after (str, optional): Insert after this cell (ID or name).
                Mutually exclusive with `before`.
            hide_code (bool): Collapse the code editor in the UI.
                Defaults to True.
            disabled (bool): Prevent the cell from executing.
                Defaults to False.
            expand_output (bool): Show the cell's output in full instead of
                clamping it to a fixed height. Defaults to False.
            column (int, optional): Column index for multi-column layouts.
            name (str, optional): New name for the cell. Must be a valid Python
                identifier. `None` creates an unnamed cell. Names are reserved
                for special cases (for example, `"setup"`). Prefer the
                returned cell ID unless naming is important.
        """
        self._require_entered()
        if before is not None and after is not None:
            raise ValueError("Cannot specify both 'before' and 'after'")

        _validate_cell_name(name)
        cell_id, resolved_name = self._resolve_new_cell(name)

        config = CellConfig(
            hide_code=hide_code,
            disabled=disabled,
            expand_output=expand_output,
            column=column,
        )

        before_id = (
            self._resolve_target(before) if before is not None else None
        )
        after_id = self._resolve_target(after) if after is not None else None

        op = _AddOp(
            cell_id=cell_id,
            code=code,
            config=config,
            before=before_id,
            after=after_id,
            name=resolved_name,
        )
        self._ops.append(op)
        self._pending_adds[cell_id] = op
        return cell_id

    def _current_config(self, cell_id: CellId_t) -> CellConfig:
        """The cell's config as of the last op queued in this batch.

        Ops aren't applied to the kernel until the context exits, so a
        cell created or configured earlier in the same batch isn't in
        `cell_metadata` yet. Scan the queue first so merging into the
        existing config doesn't clobber those pending changes.
        """
        for op in reversed(self._ops):
            if op.cell_id != cell_id or not isinstance(
                op, (_AddOp, _UpdateOp)
            ):
                continue
            if op.config is not None:
                return op.config
        return self.cells[cell_id].config

    def edit_cell(
        self,
        target: str,
        code: str | None = None,
        *,
        hide_code: bool | None = None,
        disabled: bool | None = None,
        expand_output: bool | None = None,
        column: int | None = None,
        name: str | None = None,
    ) -> None:
        """Queue an update to an existing cell's code and/or config.

        Only the arguments you explicitly pass are changed — the cell's
        existing config is preserved for any argument left as `None`.

        Editing a cell does not automatically execute it. Use `run_cell`
        to queue it for execution::

            ctx.edit_cell("my_cell", "x = 42")
            ctx.run_cell("my_cell")

        Examples:
            ```python
            # Update only code (config like hide_code is preserved)
            ctx.edit_cell("data_loader", "df = pd.read_parquet('new.parquet')")

            # Update only config (code is preserved)
            ctx.edit_cell("data_loader", hide_code=False)

            # Update both code and config
            ctx.edit_cell("data_loader", "df = load()", disabled=True)

            # Edit and run
            ctx.edit_cell("my_cell", "new_code()")
            ctx.run_cell("my_cell")

            # Rename a cell
            ctx.edit_cell("old_name", name="new_name")
            ```

        Args:
            target (str): Cell ID or cell name.
            code (str, optional): New Python source code. None keeps existing.
            hide_code (bool, optional): Collapse the code editor. None keeps existing.
            disabled (bool, optional): Prevent the cell from executing. None keeps existing.
            expand_output (bool, optional): Show the cell's output in full
                instead of clamping it to a fixed height. None keeps existing.
            column (int, optional): Column index for multi-column layouts. None keeps existing.
            name (str, optional): New name for the cell. Must be a valid Python
                identifier. `None` keeps the existing name.
        """
        self._require_entered()
        _validate_cell_name(name)
        cell_id = self._resolve_target(target)

        # Handle cell-id migration when converting to a setup cell.
        # Setup is identified by cell_id, not name — clear the name
        # and migrate to the well-known setup cell_id.
        new_cell_id: CellId_t | None = None
        if name == SETUP_CELL_NAME:
            setup_id = (
                self._cell_manager.setup_cell_id
                if self._cell_manager is not None
                else CellId_t(SETUP_CELL_NAME)
            )
            if cell_id != setup_id:
                # Check that no setup cell already exists.
                try:
                    self.cells._resolve(SETUP_CELL_NAME)
                    raise ValueError(
                        "A setup cell already exists. Use "
                        'ctx.edit_cell("setup", code=...) to modify it.'
                    )
                except KeyError:
                    pass
                new_cell_id = setup_id
                if code is None:
                    source = self._document.cell(protocol.CellId(cell_id))
                    assert source is not None
                    code = source.code
            # Setup is identified by cell_id alone — don't store a name.
            name = None

        if code is not None and not self._skip_staleness_check:
            stale = frozenset(
                CellId_t(cell.id)
                for cell in self._document
                if cell.code.strip()
                and self._kernel.agent.read_etags.get(CellId_t(cell.id))
                != cell.etag
            )
            if cell_id in stale:
                raise StaleCellError(cell_id, stale)

        # Build config only if any config kwarg was explicitly set,
        # starting from the existing config so unspecified fields persist.
        config: CellConfig | None = None
        overrides = {
            key: value
            for key, value in (
                ("hide_code", hide_code),
                ("disabled", disabled),
                ("expand_output", expand_output),
                ("column", column),
            )
            if value is not None
        }
        if overrides:
            config = structs_replace(
                self._current_config(cell_id), **overrides
            )

        self._ops.append(
            _UpdateOp(
                cell_id=cell_id,
                code=code,
                config=config,
                name=name,
                new_cell_id=new_cell_id,
            )
        )

    def delete_cell(self, target: str) -> None:
        """Queue a cell for deletion.

        Examples:
            ```python
            ctx.delete_cell("scratch")  # by name
            ctx.delete_cell("a1b2c3d4-...")  # by cell ID
            ```

        Args:
            target (str): Cell ID or cell name to delete.
        """
        self._require_entered()
        cell_id = self._resolve_target(target)
        self._ops.append(_DeleteOp(cell_id=cell_id))

    def move_cell(
        self,
        target: str,
        *,
        before: str | None = None,
        after: str | None = None,
    ) -> None:
        """Queue a cell to be repositioned in the notebook.

        Moves only affect visual ordering — they do not re-execute
        cells or change the dependency graph.

        Examples:
            ```python
            ctx.move_cell("imports", before="analysis")
            ctx.move_cell("cleanup", after="main_logic")
            ```

        Args:
            target (str): Cell ID or cell name to move.
            before (str, optional): Place before this cell (ID or name).
                Mutually exclusive with `after`.
            after (str, optional): Place after this cell (ID or name).
                Mutually exclusive with `before`.
        """
        self._require_entered()
        if before is not None and after is not None:
            raise ValueError("Cannot specify both 'before' and 'after'")
        if before is None and after is None:
            raise ValueError("Must specify either 'before' or 'after'")

        cell_id = self._resolve_target(target)
        before_id = (
            self._resolve_target(before) if before is not None else None
        )
        after_id = self._resolve_target(after) if after is not None else None

        self._ops.append(
            _MoveOp(
                cell_id=cell_id,
                before=before_id,
                after=after_id,
            )
        )

    def run_cell(self, target: str) -> None:
        """Queue a cell for execution.

        Cells created or edited in the same batch are not executed
        automatically — use `run_cell` to mark them for execution.
        Can also be used to re-run an existing cell without editing it.

        All queued `run_cell` targets are executed in a single batch
        on context exit, after structural operations (create/edit/delete)
        have been applied.

        Examples:
            ```python
            # Create and run
            cid = ctx.create_cell("x = 1")
            ctx.run_cell(cid)

            # Edit and run
            ctx.edit_cell("my_cell", code="y = 2")
            ctx.run_cell("my_cell")

            # Re-run an existing cell without editing
            ctx.run_cell("my_cell")
            ```

        Args:
            target (str): Cell ID or cell name to execute.
        """
        self._require_entered()
        cell_id = self._resolve_target(target)
        # Guard against running a cell that is queued for deletion.
        deleted_ids = {
            op.cell_id for op in self._ops if isinstance(op, _DeleteOp)
        }
        if cell_id in deleted_ids:
            raise ValueError(
                f"Cannot run cell {target!r} because it is queued "
                "for deletion in this batch"
            )
        self._cells_to_run.add(cell_id)

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    async def screenshot(
        self,
        target: int | str | NotebookCell | None = None,
        *,
        timeout_ms: int = 30_000,
        as_data_url: bool = False,
        save_to: str | PathLike[str] | None = None,
    ) -> bytes | str:
        """Capture a cell's rendered output as a PNG screenshot.

        Launches a headless Chromium browser (reused across calls)
        connected to this server in kiosk mode.

        Captures the current browser-rendered output, which may be newer
        than the frozen `NotebookCell.output` snapshot.

        Requires `playwright` + its Chromium binary::

            ctx.install_packages("playwright")
            # then once: python -m playwright install chromium

        Does **not** require `async with`.

        Args:
            target: Cell to screenshot.

                - `None` — last cell.
                - `int` — cell index (negative OK).
                - `str` — cell ID or name.
                - `NotebookCell` — e.g. `ctx.cells[0]`.

                For an object defined by a cell, resolve first::

                    cid = ctx.find_cell_defining_object(chart)
                    img = await ctx.screenshot(cid)

            timeout_ms: Max wait (ms) for the output to be visible.
            as_data_url: Return `data:image/png;base64,...` str
                instead of raw bytes.
            save_to: Also write the PNG to this path.

        Returns:
            `bytes` (PNG), or `str` (data URL) if *as_data_url*.

        Raises:
            ScreenshotError: Missing playwright, missing browser,
                unknown cell, empty output, or invisible element.
        """
        from pathlib import Path

        from marimo._code_mode.screenshot import (
            ScreenshotError,
            _ScreenshotBytes,
            _ScreenshotDataUrl,
            _ScreenshotSession,
            _to_data_url,
        )
        from marimo._messaging.context import HTTP_REQUEST_CTX

        cell_id = self._resolve_screenshot_target(target)

        # Resolve server URL from the current HTTP request context.
        request = HTTP_REQUEST_CTX.get(None)
        if request is None:
            raise ScreenshotError(
                "Cannot take screenshots: no HTTP request context "
                "available.  screenshot() must be called during cell "
                "execution (e.g. from code-mode)."
            )

        # Trusted server URL + auth token injected by the /execute
        # endpoint (from server config, not request headers).
        server_url = cast(
            "str | None", request.meta.get(SCREENSHOT_SERVER_URL_KEY)
        )
        if server_url is None:
            raise ScreenshotError(
                "Cannot take screenshots: screenshot credentials not "
                "found in request.meta.  This endpoint may not "
                "support screenshots."
            )
        screenshot_auth_token = cast(
            "str | None", request.meta.get(SCREENSHOT_AUTH_TOKEN_KEY)
        )
        screenshot_file = cast(
            "str | None", request.meta.get(SCREENSHOT_FILE_KEY)
        )

        # Lazy-init the screenshot session (browser reuse).
        if self._screenshot_session is None:
            self._screenshot_session = _ScreenshotSession(
                server_url,
                screenshot_auth_token=screenshot_auth_token,
                file_key=screenshot_file,
            )

        image = await self._screenshot_session.capture(
            cell_id, timeout_ms=timeout_ms
        )

        if save_to is not None:
            # Screenshot writes are infrequent and small; a sync write
            # keeps the API simple without meaningful blocking cost.
            Path(save_to).write_bytes(image)  # noqa: ASYNC240

        if as_data_url:
            return _ScreenshotDataUrl(_to_data_url(image))
        return _ScreenshotBytes(image)

    async def close_screenshot_session(self) -> None:
        """Close the Playwright browser opened by :meth:`screenshot`.

        Called automatically in `__aexit__`.  Call this explicitly
        when using `screenshot()` outside `async with` to avoid
        leaking a headless browser process.
        """
        if self._screenshot_session is not None:
            try:
                await self._screenshot_session.close()
            except Exception:
                LOGGER.debug(
                    "Failed to close screenshot session", exc_info=True
                )
            self._screenshot_session = None

    def _resolve_screenshot_target(
        self,
        target: int | str | NotebookCell | None,
    ) -> CellId_t:
        """Resolve a screenshot *target* to a cell ID."""
        from marimo._code_mode.screenshot import ScreenshotError

        if target is None:
            if len(self.cells) == 0:
                raise ScreenshotError(
                    "Notebook has no cells. Create and run a cell first."
                )
            return self.cells[-1].id

        if isinstance(target, bool):
            # Guard before the `int` branch — `bool` subclasses
            # `int` in Python, and `ctx.screenshot(True)` almost
            # certainly reflects a caller mistake.
            raise TypeError(
                "screenshot target cannot be a bool; pass a cell ID, "
                "cell name, integer index, or NotebookCell."
            )

        if isinstance(target, int):
            try:
                return self.cells[target].id
            except IndexError as exc:
                raise ScreenshotError(
                    f"Cell index {target} out of range "
                    f"(notebook has {len(self.cells)} cells)."
                ) from exc

        if isinstance(target, str):
            try:
                return self.cells._resolve(target)
            except KeyError as exc:
                raise ScreenshotError(
                    f"Unknown cell ID or name: {target!r}."
                ) from exc

        if isinstance(target, NotebookCell):
            return target.id

        raise TypeError(
            f"Unsupported screenshot target type: {type(target).__name__}. "
            "Pass a cell ID (str), cell name (str), integer index, "
            "or NotebookCell."
        )

    def find_cell_defining_object(self, obj: Any) -> CellId_t | None:
        """Return the cell ID whose `defs` include a variable bound to *obj*.

        Uses identity (`is`) matching against kernel globals.
        Returns `None` if no cell defines *obj*.

        Example::

            cell_id = ctx.find_cell_defining_object(chart)
            if cell_id is not None:
                image = await ctx.screenshot(cell_id)
        """
        globals_map = self.globals
        names = [name for name, value in globals_map.items() if value is obj]
        if not names:
            return None

        graph_cells = self.graph.cells

        name_set = set(names)
        for cell_id, cell_impl in graph_cells.items():
            if name_set & getattr(cell_impl, "defs", set()):
                return cell_id
        return None

    # ------------------------------------------------------------------
    # Apply queued operations
    # ------------------------------------------------------------------

    def _dry_run_compile(self, ops: list[_Op]) -> None:
        """Reject new syntax and graph errors against the document being edited."""
        baseline = DirectedGraph()
        compiled: dict[CellId_t, CellImpl] = {}
        for source in self._document:
            try:
                compiled[CellId_t(source.id)] = compile_cell(
                    source.code, cell_id=CellId_t(source.id)
                )
            except SyntaxError:
                # An existing invalid cell must not block unrelated edits.
                continue
            baseline.register_cell(
                CellId_t(source.id), compiled[CellId_t(source.id)]
            )

        graph = DirectedGraph()
        written: set[CellId_t] = set()
        for entry in _build_plan(
            [CellId_t(cell.id) for cell in self._document], ops
        ):
            if entry.code is not None:
                cell = compile_cell(entry.code, cell_id=entry.cell_id)
                written.add(entry.cell_id)
            else:
                existing_cell = compiled.get(entry.cell_id)
                if existing_cell is None:
                    continue
                cell = existing_cell
            graph.register_cell(entry.cell_id, cell)

        new_names = set(graph.get_multiply_defined()) - set(
            baseline.get_multiply_defined()
        )
        new_cycles = set(graph.cycles) - set(baseline.cycles)
        skip_hint = (
            "\n\nTo skip validation, use: "
            "async with cm.get_context(skip_validation=True) as ctx"
        )
        if new_names:
            details: list[str] = []
            for name in sorted(new_names):
                existing = graph.get_defining_cells(name) - written
                if existing:
                    labels = ", ".join(
                        self._cell_label(cid) for cid in sorted(existing)
                    )
                    details.append(
                        f"  - {name!r} is already defined in cell {labels}"
                    )
                else:
                    details.append(f"  - {name!r}")
            raise RuntimeError(
                "Multiply-defined names:\n" + "\n".join(details) + skip_hint
            )
        if new_cycles:
            raise RuntimeError(f"Cycles detected: {new_cycles}{skip_hint}")

    async def _request_document(
        self,
        *,
        changes: tuple[protocol.Change, ...] | None = None,
        cells: tuple[protocol.RequestedCell, ...] = (),
        for_run: bool = False,
    ) -> DocumentReplyCommand:
        reply = await self._kernel.document_requests.request(
            DocumentRequest(
                request_id=str(uuid4()),
                changes=changes,
                cells=cells,
                for_run=for_run,
                applied_edits=tuple(sorted(self._kernel.inline_edits)),
            )
        )
        if reply.problem is not None:
            detail = reply.problem.detail
            raise RuntimeError(
                detail if isinstance(detail, str) else reply.problem.title
            )
        assert reply.document is not None
        self._document = reply.document.document()
        self._scratch_document.document = self._document
        self._id_generator.seen_ids.update(
            CellId_t(cell.id) for cell in self._document
        )
        return reply

    async def _flush_document(
        self, ops: list[_Op], run_ids: set[CellId_t]
    ) -> None:
        document = self._document
        requested = {
            cell.id: cell.etag
            for cell in document
            if CellId_t(cell.id) in run_ids
        }
        affected: set[CellId_t] = set()
        if ops:
            _validate_ops(ops)
            if not self._skip_validation:
                self._dry_run_compile(ops)
            plan = await self._format_plan(
                _build_plan(
                    [CellId_t(cell.id) for cell in self._document], ops
                )
            )
            changes = tuple(_document_changes(document, plan))
            reply = await self._request_document(
                changes=changes, for_run=bool(run_ids)
            )
            written = {
                change.cell.id
                for change in changes
                if isinstance(change, protocol.PutCell)
            }
            affected = self._kernel.apply_document(
                self._document,
                before=document,
                written=written,
                run_ids=set(),
                edit_id=reply.inline_id,
            )
            source_writes = {
                protocol.CellId(
                    op.cell_id
                    if isinstance(op, _AddOp)
                    else op.new_cell_id or op.cell_id
                )
                for op in ops
                if isinstance(op, _AddOp)
                or isinstance(op, _UpdateOp)
                and op.code is not None
            }
            for cell_id in written:
                cell = self._document.cell(cell_id)
                assert cell is not None
                prior = document.cell(cell_id)
                if cell_id in source_writes or (
                    prior is not None
                    and self._kernel.agent.read_etags.get(CellId_t(cell_id))
                    == prior.etag
                ):
                    self._kernel.agent.read_etags[CellId_t(cell_id)] = (
                        cell.etag
                    )
                if CellId_t(cell_id) in run_ids:
                    requested[cell_id] = cell.etag
        if run_ids:
            run_ids = run_ids & {CellId_t(cell.id) for cell in self._document}
            targets = run_ids
            if self._kernel.reactive_execution_mode == "autorun":
                targets = targets | affected
            cells = tuple(
                protocol.RequestedCell(
                    id=cell.id, etag=requested.get(cell.id, cell.etag)
                )
                for cell in self._document
                if CellId_t(cell.id) in targets
            )
            if not cells:
                return
            await self._request_document(cells=cells)
            affected |= self._kernel.apply_document(
                self._document,
                before=self._document,
                written=set(),
                run_ids=run_ids,
            )
            if self._kernel.reactive_execution_mode == "autorun":
                run_ids = run_ids | affected
            await self._kernel._run_cells(run_ids & set(self.graph.cells))

    async def _format_plan(self, plan: list[_PlanEntry]) -> list[_PlanEntry]:
        """Format new/changed code when save-time formatting is enabled."""
        if not self._kernel.user_config.save.format_on_save:
            return plan

        existing_code = {
            CellId_t(cell.id): cell.code for cell in self._document
        }

        to_format: dict[CellId_t, str] = {}
        for entry in plan:
            if entry.code is not None and entry.code != existing_code.get(
                entry.cell_id
            ):
                to_format[entry.cell_id] = entry.code

        if not to_format:
            return plan

        try:
            line_length = self._kernel.user_config.formatting.line_length
            formatter = DefaultFormatter(line_length=line_length)
            formatted = await formatter.format(
                to_format,
                stdin_filename=self._kernel.app_metadata.filename,
            )
        except Exception:
            LOGGER.debug("Auto-format skipped: no formatter available")
            return plan

        for entry in plan:
            if entry.cell_id in formatted:
                entry.code = formatted[entry.cell_id]
        return plan

    # ------------------------------------------------------------------
    # UI elements
    # ------------------------------------------------------------------

    def set_ui_value(self, element: Any, value: Any) -> None:
        """Queue a UI element value update.

        Triggers reactive re-execution the same way a user interaction
        would. Updates are flushed as a single batch on context exit.

        Examples:
            ```python
            slider = ctx.globals["my_slider"]
            ctx.set_ui_value(slider, 42)

            dropdown = ctx.globals["color_picker"]
            ctx.set_ui_value(dropdown, "red")
            ```

        Args:
            element: A marimo UI element (e.g. `mo.ui.slider`).
            value: The new value, matching the type the element expects.
        """
        self._require_entered()
        self._ui_updates.append((UIElementId(element._id), value))

    # ------------------------------------------------------------------
    # Low-level primitives
    # ------------------------------------------------------------------

    async def execute_command(self, command: CommandMessage) -> None:
        """Execute a command inline and await completion."""
        try:
            await self._kernel.handle_message(command)
        except Exception:
            LOGGER.exception(
                "Failed to execute command: %s",
                type(command).__name__,
            )

    def enqueue_command(self, command: CommandMessage) -> None:
        """Fire-and-forget: runs after the current cell finishes."""
        try:
            self._kernel.enqueue_control_request(command)
        except Exception:
            LOGGER.exception(
                "Failed to enqueue command: %s",
                type(command).__name__,
            )

    def broadcast_raw_notification(self, notification: Notification) -> None:
        """Low-level: broadcast a fully-constructed `Notification` to the frontend.

        Escape hatch for emitting notification payloads directly; the
        payload is delivered as-is, with no validation, batching, or
        debouncing. Prefer a higher-level helper on `ctx` when one exists.

        See `marimo._messaging.notification` for the full discriminated
        union. Agent-facing subtypes include `BannerNotification` (persistent
        banner) and `AlertNotification` (modal dialog).
        """
        broadcast_notification(notification, stream=self._kernel.stream)  # type: ignore[arg-type]
