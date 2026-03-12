# Copyright 2026 Marimo. All rights reserved.
"""AsyncCodeModeContext: programmatic access to act on behalf of the user.

.. warning::

    **Internal, agent-only API.** Not part of marimo's public API.
    No versioning guarantees. May change or be removed without notice.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, overload

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
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.runtime import CellMetadata
from marimo._types.ids import CellId_t, UIElementId
from marimo._utils.formatter import DefaultFormatter

if TYPE_CHECKING:
    from marimo._ast.cell_manager import CellManager
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._runtime.runtime import Kernel


def get_context() -> AsyncCodeModeContext:
    """Return the AsyncCodeModeContext for the running kernel.

    Must be called from within a running marimo kernel (e.g., scratchpad).
    Make sure to ``await`` all cell operations on the returned context.
    """

    runtime_ctx = _get_runtime_context()
    if not isinstance(runtime_ctx, KernelRuntimeContext):
        raise RuntimeError("code mode requires a running kernel context")  # noqa: TRY004
    cell_manager = runtime_ctx._app._cell_manager if runtime_ctx._app else None
    return AsyncCodeModeContext(runtime_ctx._kernel, cell_manager=cell_manager)


class _CellsView:
    """Read-only view over notebook cells as ``NotebookCellData`` objects.

    Supports lookup by integer index, cell ID, or cell name::

        ctx.cells[0]                   # by index
        ctx.cells[-1]                  # negative index
        ctx.cells["Abcd1234"]          # by cell ID
        ctx.cells["my_cell"]           # by cell name
    """

    def __init__(self, ctx: AsyncCodeModeContext) -> None:
        self._ctx = ctx

    def _cell_ids(self) -> list[CellId_t]:
        return list(self._ctx.graph.cells.keys())

    def _cell_name(self, cell_id: CellId_t) -> str | None:
        cm = self._ctx._cell_manager
        if cm is None:
            return None
        data = cm.get_cell_data(cell_id)
        return data.name if data else None

    def _build_at(self, cell_id: CellId_t, index: int) -> NotebookCellData:
        cell_impl = self._ctx.graph.cells[cell_id]
        meta = self._ctx._kernel.cell_metadata.get(cell_id)
        return NotebookCellData(
            code=cell_impl.code,
            config=meta.config if meta else CellConfig(),
            name=self._cell_name(cell_id),
            cell_id=cell_id,
            _index=index,
        )

    def __len__(self) -> int:
        return len(self._ctx.graph.cells)

    @overload
    def __getitem__(self, key: int) -> NotebookCellData: ...
    @overload
    def __getitem__(self, key: str) -> NotebookCellData: ...

    def __getitem__(self, key: int | str) -> NotebookCellData:
        cell_ids = self._cell_ids()

        if isinstance(key, int):
            # Normalize negative indices for the stored _index.
            idx = key if key >= 0 else len(cell_ids) + key
            return self._build_at(cell_ids[key], idx)

        # String key — try cell ID first, then cell name.
        cell_id_key = CellId_t(key)
        for idx, cid in enumerate(cell_ids):
            if cid == cell_id_key:
                return self._build_at(cid, idx)

        # Fall back to matching against cell name.
        for idx, cid in enumerate(cell_ids):
            name = self._cell_name(cid)
            if name == key:
                return self._build_at(cid, idx)

        raise KeyError(key)

    def __iter__(self) -> Iterator[NotebookCellData]:
        cell_ids = self._cell_ids()
        for i, cid in enumerate(cell_ids):
            yield self._build_at(cid, i)


@dataclass
class _PlanEntry:
    """A single slot in the edit plan."""

    cell_id: CellId_t
    code: str | None = None
    config: CellConfig | None = None
    draft: bool = False


def _build_plan(
    existing_cell_ids: Sequence[CellId_t],
    edits: Sequence[Edit],
) -> list[_PlanEntry]:
    """Reduce a sequence of edits into a flat plan.

    Pure function — no graph or kernel access. The returned plan
    describes the target cell list after all edits are applied.
    """
    plan: list[_PlanEntry] = [
        _PlanEntry(cell_id=cid) for cid in existing_cell_ids
    ]

    for edit in edits:
        if isinstance(edit, _InsertCells):
            for offset, cell_data in enumerate(edit.cells):
                if cell_data.code is None:
                    raise ValueError("code is required when inserting a cell")
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

    return plan


class AsyncCodeModeContext:
    """Async programmatic control of a running marimo notebook.

    Build edits with ``NotebookEdit`` static methods, apply them with
    ``await ctx.apply_edit(edits)``. Read cells via ``ctx.cells[key]``
    where *key* is an integer index, cell ID string, or cell name.

    Tip: check this module's imports for where types live.
    """

    def __init__(
        self,
        kernel: Kernel,
        cell_manager: CellManager | None = None,
    ) -> None:
        self._kernel = kernel
        self._cell_manager = cell_manager

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
        """Read-only view of notebook cells as ``NotebookCellData`` objects.

        Supports lookup by index, cell ID, or cell name::

            ctx.cells[0]              # by index
            ctx.cells["cell-id"]      # by cell ID (CellId_t string)
            ctx.cells["my_cell"]      # by cell name (function def name)
        """
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

        # -- Phase 1: reduce edits to a plan --
        existing_ids = list(self.graph.cells.keys())
        plan = _build_plan(existing_ids, edits)

        # -- Phase 1.5: auto-format new/changed code --
        plan = await self._format_plan(plan)

        # -- Phase 2: reconcile plan against the graph --

        existing_id_set = set(self.graph.cells.keys())
        # Snapshot existing code so we can detect true changes vs moves
        existing_code = {
            cid: self.graph.cells[cid].code for cid in existing_id_set
        }
        plan_ids = {e.cell_id for e in plan}

        # Delete cells that are in the graph but not in the plan
        for cid in existing_id_set - plan_ids:
            self.graph.delete_cell(cid)
            self._kernel.cell_metadata.pop(cid, None)

        # Insert/update cells and collect what needs executing
        cells_to_execute: list[tuple[CellId_t, str]] = []
        code_notifications: list[_PlanEntry] = []

        for entry in plan:
            is_new = entry.cell_id not in existing_id_set
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

        # Group code notifications by draft status so each batch has a
        # single code_is_stale value, and include configs.
        by_stale: dict[bool, list[_PlanEntry]] = {}
        for entry in code_notifications:
            by_stale.setdefault(entry.draft, []).append(entry)

        for is_stale, entries in by_stale.items():
            self.notify(
                UpdateCellCodesNotification(
                    cell_ids=[e.cell_id for e in entries],
                    codes=[
                        # code is guaranteed non-None for code_notifications
                        e.code  # type: ignore[misc]
                        for e in entries
                    ],
                    code_is_stale=is_stale,
                    configs=[
                        e.config or CellConfig(hide_code=True) for e in entries
                    ],
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
        try:
            await self._kernel.handle_message(command)
        except Exception:
            self.LOGGER.exception(
                "Failed to execute command: %s",
                type(command).__name__,
            )

    def enqueue_command(self, command: CommandMessage) -> None:
        """Fire-and-forget: runs after the current cell finishes.

        See ``marimo._runtime.commands`` for available types.
        """
        try:
            self._kernel.enqueue_control_request(command)
        except Exception:
            self.LOGGER.exception(
                "Failed to enqueue command: %s",
                type(command).__name__,
            )

    def notify(self, notification: Notification) -> None:
        """Send a notification to the frontend.

        See ``marimo._messaging.notification`` for available types.
        """
        broadcast_notification(notification, stream=self._kernel.stream)  # type: ignore[arg-type]
