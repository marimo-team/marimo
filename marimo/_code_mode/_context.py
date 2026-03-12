# Copyright 2026 Marimo. All rights reserved.
"""AsyncCodeModeContext: programmatic access to act on behalf of the user.

.. warning::

    **Internal, agent-only API.** Not part of marimo's public API.
    No versioning guarantees. May change or be removed without notice.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Any

from dataclasses import dataclass

from marimo import _loggers
from marimo._ast.cell import CellConfig
from marimo._ast.compiler import compile_cell
from marimo._code_mode._edits import (
    Edit,
    NotebookCellData,
    _DeleteCells,
    _InsertCells,
    _ReplaceCells,
)
from marimo._messaging.notification import (
    Notification,
    UpdateCellCodesNotification,
    UpdateCellIdsNotification,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.commands import (
    CommandMessage,
    ExecuteCellsCommand,
    UpdateCellConfigCommand,
    UpdateUIElementCommand,
)
from marimo._runtime.context import get_context as _get_runtime_context
from marimo._runtime.runtime import CellMetadata
from marimo._types.ids import CellId_t, UIElementId

if TYPE_CHECKING:
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._runtime.runtime import Kernel


def get_context() -> AsyncCodeModeContext:
    """Return the AsyncCodeModeContext for the running kernel.

    Must be called from within a running marimo kernel (e.g., scratchpad).
    Make sure to ``await`` all cell operations on the returned context.
    """
    from marimo._runtime.context.kernel_context import KernelRuntimeContext

    runtime_ctx = _get_runtime_context()
    if not isinstance(runtime_ctx, KernelRuntimeContext):
        raise RuntimeError("code mode requires a running kernel context")  # noqa: TRY004
    return AsyncCodeModeContext(runtime_ctx._kernel)


class _CellsView:
    """List-like read-only view over notebook cells as ``NotebookCellData`` objects."""

    def __init__(self, ctx: AsyncCodeModeContext) -> None:
        self._ctx = ctx

    def _cell_ids(self) -> list[CellId_t]:
        return list(self._ctx.graph.cells.keys())

    def __len__(self) -> int:
        return len(self._ctx.graph.cells)

    def __getitem__(self, index: int) -> NotebookCellData:
        cell_ids = self._cell_ids()
        cell_id = cell_ids[index]
        cell_impl = self._ctx.graph.cells[cell_id]
        config = self._ctx._kernel.cell_metadata.get(cell_id)
        return NotebookCellData(
            code=cell_impl.code,
            config=config.config if config else CellConfig(),
            cell_id=cell_id,
            _index=index,
        )

    def __iter__(self) -> Iterator[NotebookCellData]:
        for i in range(len(self)):
            yield self[i]


@dataclass
class _PlanEntry:
    """A single slot in the edit plan."""

    cell_id: CellId_t
    code: str | None = None
    config: CellConfig | None = None
    draft: bool = False


class AsyncCodeModeContext:
    """Async programmatic control of a running marimo notebook.

    Build edits with ``NotebookEdit`` static methods, apply them with
    ``await ctx.apply_edit(edits)``. Read cells via ``ctx.cells[index]``.

    Tip: check this module's imports for where types live.
    """

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel

    # ------------------------------------------------------------------
    # Read-only attributes
    # ------------------------------------------------------------------

    @property
    def graph(self) -> DirectedGraph:
        """The notebook's dependency graph (cells, defs, refs, config)."""
        return self._kernel.graph

    @property
    def globals(self) -> dict[str, Any]:
        """The kernel's global namespace (all variables defined by cells)."""
        return self._kernel.globals

    @property
    def cells(self) -> _CellsView:
        """Read-only view of notebook cells as ``NotebookCellData`` objects."""
        return _CellsView(self)

    # ------------------------------------------------------------------
    # Apply edits
    # ------------------------------------------------------------------

    async def apply_edit(self, edits: Edit | Sequence[Edit]) -> None:
        """Apply one or more notebook edits.

        Edits are reduced into a single plan (target ordering + mutations)
        before anything touches the graph. This means delete + insert of
        the same cell naturally becomes a move.

        New and changed cell code is auto-formatted with ruff (or black)
        before compilation. If no formatter is available, code is used as-is.
        """
        if not isinstance(edits, Sequence):
            edits = [edits]

        # -- Phase 1: reduce edits to a plan against a virtual cell list --
        # None code means "keep existing".
        plan: list[_PlanEntry] = [
            _PlanEntry(cell_id=cid) for cid in self.graph.cells
        ]

        for edit in edits:
            if isinstance(edit, _InsertCells):
                for offset, cell_data in enumerate(edit.cells):
                    if cell_data.code is None:
                        raise ValueError(
                            "code is required when inserting a cell"
                        )
                    idx = min(edit.index + offset, len(plan))
                    plan.insert(
                        idx,
                        _PlanEntry(
                            cell_id=cell_data.cell_id,
                            code=cell_data.code,
                            config=cell_data.config,
                            draft=cell_data.draft,
                        ),
                    )

            elif isinstance(edit, _DeleteCells):
                del plan[edit.start : edit.end]

            elif isinstance(edit, _ReplaceCells):
                for offset, cell_data in enumerate(edit.cells):
                    target_idx = edit.index + offset
                    if target_idx >= len(plan):
                        raise IndexError(
                            f"Index {target_idx} out of range "
                            f"(plan has {len(plan)} cells)"
                        )
                    entry = plan[target_idx]
                    entry.code = cell_data.code  # None = keep existing
                    if cell_data.config is not None:
                        entry.config = cell_data.config
                    entry.draft = cell_data.draft

            else:
                raise TypeError(f"Unknown edit type: {type(edit)!r}")

        # -- Phase 1.5: auto-format new/changed code --
        plan = await self._format_plan(plan)

        # -- Phase 2: reconcile plan against the graph --

        existing_ids = set(self.graph.cells.keys())
        # Snapshot existing code so we can detect true changes vs moves
        existing_code = {
            cid: self.graph.cells[cid].code for cid in existing_ids
        }
        plan_ids = {e.cell_id for e in plan}

        # Delete cells that are in the graph but not in the plan
        for cid in existing_ids - plan_ids:
            self.graph.delete_cell(cid)
            self._kernel.cell_metadata.pop(cid, None)

        # Insert/update cells and collect what needs executing
        cells_to_execute: list[tuple[CellId_t, str]] = []
        code_notifications: list[_PlanEntry] = []

        for entry in plan:
            is_new = entry.cell_id not in existing_ids
            code_changed = (
                entry.code is not None
                and entry.code != existing_code.get(entry.cell_id)
            )

            if is_new:
                # New cell — must have code
                assert entry.code is not None
                cfg = entry.config or CellConfig(hide_code=True)
                cell = compile_cell(entry.code, cell_id=entry.cell_id)
                cell.configure(cfg.asdict())
                self._kernel.cell_metadata[entry.cell_id] = CellMetadata(
                    config=cfg
                )
                self.graph.register_cell(entry.cell_id, cell)
                code_notifications.append(entry)
                if not entry.draft:
                    cells_to_execute.append((entry.cell_id, entry.code))

            elif code_changed:
                # Existing cell with genuinely new code
                assert entry.code is not None
                self.graph.delete_cell(entry.cell_id)
                cell = compile_cell(entry.code, cell_id=entry.cell_id)
                if entry.config is not None:
                    cell.configure(entry.config.asdict())
                    self._kernel.cell_metadata[entry.cell_id] = CellMetadata(
                        config=entry.config
                    )
                self.graph.register_cell(entry.cell_id, cell)
                code_notifications.append(entry)
                if not entry.draft:
                    cells_to_execute.append((entry.cell_id, entry.code))

            elif entry.config is not None:
                # Config-only update
                await self.execute_command(
                    UpdateCellConfigCommand(
                        configs={entry.cell_id: entry.config.asdict()}
                    )
                )

        # -- Phase 3: notify frontend and execute --
        target_order = [e.cell_id for e in plan]
        for entry in code_notifications:
            assert entry.code is not None
            self.notify(
                UpdateCellCodesNotification(
                    cell_ids=[entry.cell_id],
                    codes=[entry.code],
                    code_is_stale=entry.draft,
                )
            )

        self.notify(UpdateCellIdsNotification(cell_ids=target_order))

        if cells_to_execute:
            ids, codes = zip(*cells_to_execute)
            await self.execute_command(
                ExecuteCellsCommand(cell_ids=list(ids), codes=list(codes))
            )

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    LOGGER = _loggers.marimo_logger()

    async def _format_plan(self, plan: list[_PlanEntry]) -> list[_PlanEntry]:
        """Format new/changed code in the plan with the default formatter."""
        from marimo._utils.formatter import DefaultFormatter

        existing_code = {
            cid: self.graph.cells[cid].code for cid in self.graph.cells
        }

        # Collect codes that need formatting (new or changed)
        to_format: dict[CellId_t, str] = {}
        for entry in plan:
            if entry.code is not None and entry.code != existing_code.get(
                entry.cell_id
            ):
                to_format[entry.cell_id] = entry.code

        if not to_format:
            return plan

        try:
            formatter = DefaultFormatter(line_length=79)
            formatted = await formatter.format(to_format)
        except Exception:
            self.LOGGER.debug("Auto-format skipped: no formatter available")
            return plan

        # Apply formatted code back to plan entries
        for entry in plan:
            if entry.cell_id in formatted:
                entry.code = formatted[entry.cell_id]
        return plan

    # ------------------------------------------------------------------
    # UI elements
    # ------------------------------------------------------------------

    async def set_ui_value(self, element: Any, value: Any) -> None:
        """Set a UI element's value and re-run dependent cells.

        The element must have an ``_id`` attribute (any ``marimo.ui`` widget).
        """
        element_id = UIElementId(element._id)
        await self._kernel.set_ui_element_value(
            UpdateUIElementCommand(
                object_ids=[element_id],
                values=[value],
            )
        )

    # ------------------------------------------------------------------
    # Low-level primitives
    # ------------------------------------------------------------------

    async def execute_command(self, command: CommandMessage) -> None:
        """Execute a command inline and await completion.

        See ``marimo._runtime.commands`` for available types.
        """
        await self._kernel.handle_message(command)

    def enqueue_command(self, command: CommandMessage) -> None:
        """Fire-and-forget: runs after the current cell finishes.

        See ``marimo._runtime.commands`` for available types.
        """
        self._kernel.enqueue_control_request(command)

    def notify(self, notification: Notification) -> None:
        """Send a notification to the frontend.

        See ``marimo._messaging.notification`` for available types.
        """
        broadcast_notification(notification, stream=self._kernel.stream)  # type: ignore[arg-type]
