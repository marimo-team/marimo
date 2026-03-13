# Copyright 2026 Marimo. All rights reserved.
"""AsyncCodeModeContext: programmatic notebook editing via async context manager.

.. warning::

    **Internal, agent-only API.** Not part of marimo's public API.
    No versioning guarantees. May change or be removed without notice.

Usage::

    import marimo._code_mode as cm

    async with cm.get_context() as ctx:
        cid = ctx.create_cell("x = 1")
        ctx.create_cell("y = x + 1", after=cid)
        ctx.update_cell("my_cell", code="z = 42")
        ctx.delete_cell("old_cell")
        ctx.move_cell("my_cell", after="other_cell")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, overload
from uuid import uuid4

from marimo import _loggers
from marimo._ast.cell import CellConfig, CellImpl
from marimo._ast.compiler import compile_cell
from marimo._code_mode._plan import (
    _AddOp,
    _build_plan,
    _DeleteOp,
    _MoveOp,
    _Op,
    _PlanEntry,
    _UpdateOp,
    _validate_ops,
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
    InstallPackagesCommand,
    UpdateCellConfigCommand,
    UpdateUIElementCommand,
)
from marimo._runtime.context import get_context as _get_runtime_context
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.runtime import CellMetadata
from marimo._types.ids import CellId_t, UIElementId
from marimo._utils.formatter import DefaultFormatter

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import TracebackType

    from marimo._ast.cell_manager import CellManager
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._runtime.runtime import Kernel


# ------------------------------------------------------------------
# Data types
# ------------------------------------------------------------------


@dataclass(frozen=True)
class NotebookCellData:
    """Read-only snapshot of a notebook cell (returned by ``ctx.cells[...]``)."""

    code: str | None = None
    config: CellConfig | None = None
    cell_id: CellId_t = field(default_factory=lambda: CellId_t(str(uuid4())))
    name: str | None = field(default=None, repr=True, compare=False)


LOGGER = _loggers.marimo_logger()


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def get_context(*, check: bool = True) -> AsyncCodeModeContext:
    """Return an ``AsyncCodeModeContext`` for the running kernel.

    Use as an async context manager::

        async with cm.get_context() as ctx:
            ctx.create_cell("x = 1")

    By default, a dry-run compile check is performed on exit to catch
    syntax errors, multiply-defined names, and cycles before any graph
    mutations.  Pass ``check=False`` to skip this validation::

        async with cm.get_context(check=False) as ctx:
            ...
    """
    runtime_ctx = _get_runtime_context()
    if not isinstance(runtime_ctx, KernelRuntimeContext):
        raise RuntimeError("code mode requires a running kernel context")  # noqa: TRY004
    cell_manager = runtime_ctx._app.cell_manager if runtime_ctx._app else None
    return AsyncCodeModeContext(
        runtime_ctx._kernel, cell_manager=cell_manager, check=check
    )


class _CellsView:
    """Read-only view over notebook cells as ``NotebookCellData`` objects.

    Supports lookup by integer index, cell ID, or cell name::

        ctx.cells[0]  # by index
        ctx.cells[-1]  # negative index
        ctx.cells["Abcd1234"]  # by cell ID
        ctx.cells["my_cell"]  # by cell name
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

    def _build_at(self, cell_id: CellId_t) -> NotebookCellData:
        cell_impl = self._ctx.graph.cells[cell_id]
        meta = self._ctx._kernel.cell_metadata.get(cell_id)
        return NotebookCellData(
            code=cell_impl.code,
            config=meta.config if meta else CellConfig(),
            name=self._cell_name(cell_id),
            cell_id=cell_id,
        )

    def _resolve(self, target: str) -> CellId_t:
        """Resolve a cell ID or cell name to a ``CellId_t``.

        Raises ``KeyError`` if not found.
        """
        cell_ids = self._cell_ids()

        # Try cell ID first.
        cell_id_key = CellId_t(target)
        for cid in cell_ids:
            if cid == cell_id_key:
                return cid

        # Fall back to cell name.
        for cid in cell_ids:
            name = self._cell_name(cid)
            if name == target:
                return cid

        raise KeyError(target)

    def __len__(self) -> int:
        return len(self._ctx.graph.cells)

    @overload
    def __getitem__(self, key: int) -> NotebookCellData: ...
    @overload
    def __getitem__(self, key: str) -> NotebookCellData: ...

    def __getitem__(self, key: int | str) -> NotebookCellData:
        cell_ids = self._cell_ids()

        if isinstance(key, int):
            return self._build_at(cell_ids[key])

        return self._build_at(self._resolve(key))

    def __iter__(self) -> Iterator[NotebookCellData]:
        for cid in self._cell_ids():
            yield self._build_at(cid)


# ------------------------------------------------------------------
# Context
# ------------------------------------------------------------------


class AsyncCodeModeContext:
    """Async programmatic control of a running marimo notebook.

    Use as an async context manager — mutations are queued during the
    block and applied atomically on exit::

        async with cm.get_context() as ctx:
            ctx.create_cell("x = 1")
            ctx.update_cell("my_cell", code="x = 42")
            ctx.delete_cell("old_cell")

    Read cells via ``ctx.cells[key]`` where *key* is an integer index,
    cell ID string, or cell name.
    """

    def __init__(
        self,
        kernel: Kernel,
        cell_manager: CellManager | None = None,
        *,
        check: bool = True,
    ) -> None:
        self._kernel = kernel
        self._cell_manager = cell_manager
        self._check = check
        self._ops: list[_Op] = []
        # Track cell IDs added during this batch so subsequent ops
        # can reference them before they exist in the graph.
        self._pending_adds: dict[CellId_t, _AddOp] = {}
        self._packages_to_install: list[str] = []
        self._ui_updates: list[tuple[UIElementId, Any]] = []
        self._entered = False

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

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> AsyncCodeModeContext:
        self._ops = []
        self._pending_adds = {}
        self._packages_to_install = []
        self._ui_updates = []
        self._entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        ops = self._ops
        packages = self._packages_to_install
        ui_updates = self._ui_updates
        self._ops = []
        self._pending_adds = {}
        self._packages_to_install = []
        self._ui_updates = []

        if exc_type is not None:
            return  # let exception propagate, discard queued ops

        # Install queued packages before applying cell ops so that
        # newly added cells can import them.
        if packages:
            manager = self._kernel.user_config["package_management"]["manager"]
            for pkg in packages:
                await self.execute_command(
                    InstallPackagesCommand(manager=manager, versions={pkg: ""})
                )

        if ops:
            _validate_ops(ops)
            if self._check:
                self._dry_run_compile(ops)
            await self._apply_ops(ops)

        # Flush queued UI updates as a single batch.
        if ui_updates:
            object_ids, values = zip(*ui_updates)
            await self._kernel.set_ui_element_value(
                UpdateUIElementCommand(
                    object_ids=list(object_ids),
                    values=list(values),
                )
            )

    # ------------------------------------------------------------------
    # Read-only attributes
    # ------------------------------------------------------------------

    @property
    def graph(self) -> DirectedGraph:
        """The notebook's dependency graph."""
        return self._kernel.graph

    @property
    def globals(self) -> dict[str, Any]:
        """The kernel's global namespace (all variables defined by cells)."""
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

    # ------------------------------------------------------------------
    # Mutation methods (queue ops, applied on __aexit__)
    # ------------------------------------------------------------------

    def _resolve_target(self, target: str) -> CellId_t:
        """Resolve a cell ID or name to a ``CellId_t``.

        Checks the live graph first, then pending adds.
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

        raise KeyError(
            f"Cell {target!r} not found in notebook or pending adds"
        )

    def create_cell(
        self,
        code: str,
        *,
        before: str | None = None,
        after: str | None = None,
        hide_code: bool = True,
        disabled: bool = False,
        column: int | None = None,
        draft: bool = False,
    ) -> CellId_t:
        """Queue a new cell. Returns the new cell's ID.

        The returned ID can be used in subsequent operations within the
        same batch (e.g. as an ``after`` target for the next cell).

        Examples:
            ```python
            # Append at the end
            cid = ctx.create_cell("import pandas as pd")

            # Chain cells in order
            cid2 = ctx.create_cell("df = pd.read_csv('data.csv')", after=cid)
            ctx.create_cell("df.head()", after=cid2)

            # Insert before a named cell, with code visible
            ctx.create_cell("# Setup", before="analysis", hide_code=False)

            # Stage without executing
            ctx.create_cell("expensive_computation()", draft=True)
            ```

        Args:
            code (str): Python source code for the cell.
            before (str, optional): Insert before this cell (ID or name).
                Mutually exclusive with ``after``.
            after (str, optional): Insert after this cell (ID or name).
                Mutually exclusive with ``before``.
            hide_code (bool): Collapse the code editor in the UI.
                Defaults to True.
            disabled (bool): Prevent the cell from executing.
                Defaults to False.
            column (int, optional): Column index for multi-column layouts.
            draft (bool): Insert code without executing it.
                Defaults to False.
        """
        self._require_entered()
        if before is not None and after is not None:
            raise ValueError("Cannot specify both 'before' and 'after'")

        cell_id = CellId_t(str(uuid4()))
        config = CellConfig(
            hide_code=hide_code, disabled=disabled, column=column
        )

        before_id = (
            self._resolve_target(before) if before is not None else None
        )
        after_id = self._resolve_target(after) if after is not None else None

        op = _AddOp(
            cell_id=cell_id,
            code=code,
            config=config,
            draft=draft,
            before=before_id,
            after=after_id,
        )
        self._ops.append(op)
        self._pending_adds[cell_id] = op
        return cell_id

    def update_cell(
        self,
        target: str,
        *,
        code: str | None = None,
        hide_code: bool | None = None,
        disabled: bool | None = None,
        column: int | None = None,
        draft: bool = False,
    ) -> None:
        """Queue an update to an existing cell's code and/or config.

        Only the arguments you explicitly pass are changed — the cell's
        existing config is preserved for any argument left as ``None``.

        Examples:
            ```python
            # Update only code (config like hide_code is preserved)
            ctx.update_cell(
                "data_loader", code="df = pd.read_parquet('new.parquet')"
            )

            # Update only config (code is preserved)
            ctx.update_cell("data_loader", hide_code=False)

            # Update both code and config
            ctx.update_cell("data_loader", code="df = load()", disabled=True)

            # Stage new code without executing
            ctx.update_cell("my_cell", code="new_code()", draft=True)
            ```

        Args:
            target (str): Cell ID or cell name.
            code (str, optional): New Python source code. None keeps existing.
            hide_code (bool, optional): Collapse the code editor. None keeps existing.
            disabled (bool, optional): Prevent the cell from executing. None keeps existing.
            column (int, optional): Column index for multi-column layouts. None keeps existing.
            draft (bool): Update code without executing. Defaults to False.
        """
        self._require_entered()
        cell_id = self._resolve_target(target)

        # Build config only if any config kwarg was explicitly set.
        config: CellConfig | None = None
        if hide_code is not None or disabled is not None or column is not None:
            # Start from existing config and override provided fields.
            meta = self._kernel.cell_metadata.get(cell_id)
            existing = meta.config if meta else CellConfig()
            config = CellConfig(
                hide_code=hide_code
                if hide_code is not None
                else existing.hide_code,
                disabled=disabled
                if disabled is not None
                else existing.disabled,
                column=column if column is not None else existing.column,
            )

        self._ops.append(
            _UpdateOp(
                cell_id=cell_id,
                code=code,
                config=config,
                draft=draft,
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
                Mutually exclusive with ``after``.
            after (str, optional): Place after this cell (ID or name).
                Mutually exclusive with ``before``.
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

    # ------------------------------------------------------------------
    # Apply queued operations
    # ------------------------------------------------------------------

    def _dry_run_compile(self, ops: list[_Op]) -> None:
        """Compile and graph-check every op before mutating real state.

        For each op with code:
        1. ``compile_cell`` — validates syntax, extracts defs/refs.
        2. Temporarily register in the graph to detect multiply-defined
           names and cycles.
        3. Always clean up so the graph is left unchanged.

        Raises ``SyntaxError`` for invalid code or ``RuntimeError`` for
        graph conflicts (multiply-defined names, cycles).
        """
        graph = self.graph
        registered: list[CellId_t] = []
        # For updates we must evict the old cell first; remember it
        # so we can restore on cleanup.
        evicted: dict[CellId_t, CellImpl] = {}

        # Snapshot existing problems so we only flag *new* ones.
        existing_multiply_defined = set(graph.get_multiply_defined())
        existing_cycles = set(graph.cycles)

        try:
            for op in ops:
                code: str | None = getattr(op, "code", None)
                if code is None:
                    continue

                cell_id: CellId_t = op.cell_id

                # For updates, temporarily remove the existing cell so the
                # new version can be registered in its place.
                if isinstance(op, _UpdateOp) and cell_id in graph.cells:
                    evicted[cell_id] = graph.cells[cell_id]
                    graph.delete_cell(cell_id)

                cell = compile_cell(code, cell_id=cell_id)
                graph.register_cell(cell_id, cell)
                registered.append(cell_id)

            # Only error on problems *introduced* by these ops.
            new_multiply_defined = (
                set(graph.get_multiply_defined()) - existing_multiply_defined
            )
            new_cycles = set(graph.cycles) - existing_cycles

            _check_false_hint = (
                "\n\nTo skip validation, use: "
                "async with cm.get_context(check=False) as ctx"
            )
            if new_multiply_defined:
                raise RuntimeError(
                    "Multiply-defined names: "
                    f"{sorted(new_multiply_defined)}"
                    f"{_check_false_hint}"
                )
            if new_cycles:
                raise RuntimeError(
                    f"Cycles detected: {new_cycles}{_check_false_hint}"
                )
        finally:
            # Always clean up: remove dry-run cells, restore evicted ones.
            for cid in registered:
                if cid in graph.cells:
                    graph.delete_cell(cid)
            for cid, old_cell in evicted.items():
                graph.register_cell(cid, old_cell)

    async def _apply_ops(self, ops: list[_Op]) -> None:
        """Validate, plan, format, and apply a batch of operations."""
        existing_ids = list(self.graph.cells.keys())
        plan = _build_plan(existing_ids, ops)

        # Auto-format new/changed code.
        plan = await self._format_plan(plan)

        # Reconcile plan against the graph.
        existing_id_set = set(self.graph.cells.keys())
        existing_code = {
            cid: self.graph.cells[cid].code for cid in existing_id_set
        }
        plan_ids = {e.cell_id for e in plan}

        # We call Kernel._delete_cell / _deactivate_cell directly
        # rather than going through DeleteCellCommand because we need
        # synchronous graph manipulation (delete + re-register) within
        # a single atomic batch.  DeleteCellCommand would also trigger
        # _run_cells for descendants, which we handle ourselves via the
        # ExecuteCellsCommand at the end.  These are internal kernel
        # primitives that properly clean up globals, UI elements, and
        # lifecycle hooks — the raw graph.delete_cell() does not.
        for cid in existing_id_set - plan_ids:
            self._kernel._delete_cell(cid)

        # Insert/update cells.
        cells_to_execute: list[tuple[CellId_t, str]] = []
        code_notifications: list[_PlanEntry] = []

        for entry in plan:
            is_new = entry.cell_id not in existing_id_set
            code_changed = (
                entry.code is not None
                and entry.code != existing_code.get(entry.cell_id)
            )

            if is_new or code_changed:
                assert entry.code is not None
                if is_new:
                    cfg = entry.config or CellConfig(hide_code=True)
                else:
                    # Preserve existing config when none is explicitly
                    # provided.
                    existing_meta = self._kernel.cell_metadata.get(
                        entry.cell_id
                    )
                    cfg = entry.config or (
                        existing_meta.config
                        if existing_meta
                        else CellConfig()
                    )
                    self._kernel._deactivate_cell(entry.cell_id)
                cell = compile_cell(entry.code, cell_id=entry.cell_id)
                cell.configure(cfg.asdict())
                self._kernel.cell_metadata[entry.cell_id] = CellMetadata(
                    config=cfg
                )
                self.graph.register_cell(entry.cell_id, cell)
                code_notifications.append(entry)
                if not entry.draft:
                    cells_to_execute.append((entry.cell_id, entry.code))

            elif entry.config is not None:
                await self.execute_command(
                    UpdateCellConfigCommand(
                        configs={entry.cell_id: entry.config.asdict()}
                    )
                )

        # Notify frontend.
        target_order = [e.cell_id for e in plan]

        by_stale: dict[bool, list[_PlanEntry]] = {}
        for entry in code_notifications:
            by_stale.setdefault(entry.draft, []).append(entry)

        for is_stale, entries in by_stale.items():
            self.notify(
                UpdateCellCodesNotification(
                    cell_ids=[e.cell_id for e in entries],
                    codes=[e.code for e in entries],  # type: ignore[misc]
                    code_is_stale=is_stale,
                    configs=[
                        self._kernel.cell_metadata[e.cell_id].config
                        for e in entries
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

    async def _format_plan(self, plan: list[_PlanEntry]) -> list[_PlanEntry]:
        """Format new/changed code in the plan with the default formatter."""
        existing_code = {
            cid: self.graph.cells[cid].code for cid in self.graph.cells
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
            line_length = self._kernel.user_config["formatting"]["line_length"]
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
            element: A marimo UI element (e.g. ``mo.ui.slider``).
            value: The new value, matching the type the element expects.
        """
        self._require_entered()
        self._ui_updates.append((UIElementId(element._id), value))

    # ------------------------------------------------------------------
    # Package management
    # ------------------------------------------------------------------

    def install_packages(self, *packages: str) -> None:
        """Queue packages for installation on context exit.

        Installed before cell ops, so newly added cells can import them.

        Examples:
            ```python
            ctx.install_packages("pandas")
            ctx.install_packages("polars>=0.20", "numpy==1.26")
            ```

        Args:
            *packages (str): Pip-style package specifiers.
        """
        self._require_entered()
        self._packages_to_install.extend(packages)

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

    def notify(self, notification: Notification) -> None:
        """Send a notification to the frontend."""
        broadcast_notification(notification, stream=self._kernel.stream)  # type: ignore[arg-type]
