# Copyright 2026 Marimo. All rights reserved.
"""Selective execution runner for the build pipeline.

The :class:`BuildRunner` runs every statically compilable cell in
topological order and captures its defs. Decisions about what to do
with those defs (persist as a loader, elide, fall back to verbatim)
live downstream in :mod:`marimo._build.plan`; the runner is only
responsible for execution.

If a cell raises, the build is aborted with :class:`BuildExecutionError`
— a "successful" build that quietly dropped a broken cell would be
worse than a clear failure. The user can exclude a cell from the build
by making it depend (transitively) on a runtime input
(``mo.ui.*`` / ``mo.cli_args``), which causes the static classifier to
mark it ``non_compilable`` so the runner never executes it.

Structurally similar to :class:`AppScriptRunner` but intentionally
simpler: synchronous, single-shot, and the only side-effect of
executing a cell is mutating the shared ``glbls`` dict.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from marimo._messaging.types import NoopStream
from marimo._runtime import dataflow
from marimo._runtime.context.script_context import initialize_script_context
from marimo._runtime.context.types import (
    get_context,
    runtime_context_installed,
    teardown_context,
)
from marimo._runtime.exceptions import MarimoRuntimeException
from marimo._runtime.executor import ExecutionConfig, get_executor
from marimo._runtime.patches import (
    create_main_module,
    extract_docstring_from_header,
    patch_main_module_context,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._ast.app import InternalApp
    from marimo._build.classify import Classification
    from marimo._build.events import BuildProgressEvent
    from marimo._types.ids import CellId_t


class BuildExecutionError(RuntimeError):
    """A cell raised at build time. The build is aborted.

    Wraps the underlying cause so the CLI can show both *which* cell
    failed and what went wrong.
    """

    def __init__(self, cell_name: str, cause: BaseException) -> None:
        super().__init__(
            f"Cell {cell_name!r} raised {type(cause).__name__}: {cause}"
        )
        self.cell_name = cell_name


class BuildCancelled(RuntimeError):
    """Raised when ``should_cancel`` returns True between cells.

    Carries no payload — the caller already knows it asked for the
    cancellation.
    """


class BuildRunner:
    """Run every statically compilable cell of a notebook.

    Parameters
    ----------
    app:
        The loaded notebook.
    classification:
        Static classification produced by
        :func:`marimo._build.classify.classify_static`.
    progress_callback:
        Optional sink for per-cell ``cell_executing`` /
        ``cell_executed`` events. Called synchronously from the runner
        thread; keep it cheap (e.g., enqueue onto a thread-safe queue).
    should_cancel:
        Optional poll fn checked between cells. Returning True raises
        :class:`BuildCancelled` from :meth:`run`.

    Attributes:
    ----------
    captured_defs:
        After :meth:`run`, maps each successfully executed cell id to
        the globals it bound. Cells that raised aren't reached
        (the build aborts), so this is total over
        ``classification.compilable``.
    """

    def __init__(
        self,
        app: InternalApp,
        classification: Classification,
        *,
        progress_callback: Callable[[BuildProgressEvent], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> None:
        self.app = app
        self._classification = classification
        self._executor = get_executor(ExecutionConfig())
        self._progress_callback = progress_callback
        self._should_cancel = should_cancel
        self.captured_defs: dict[CellId_t, dict[str, Any]] = {}

    def run(self) -> None:
        """Execute compilable cells, populating :attr:`captured_defs`."""
        installed = False
        try:
            if not runtime_context_installed():
                initialize_script_context(
                    app=self.app,
                    stream=NoopStream(),
                    filename=self.app.filename,
                )
                installed = True
            self._run_inner()
        finally:
            if installed:
                teardown_context()

    def _run_inner(self) -> None:
        from marimo._build.events import (
            CellExecuted,
            CellExecuting,
            CellFailed,
        )

        docstring = extract_docstring_from_header(self.app._app._header)
        with patch_main_module_context(
            create_main_module(
                file=self.app.filename,
                input_override=None,
                print_override=None,
                doc=docstring,
            )
        ) as module:
            glbls: dict[str, Any] = module.__dict__
            setup_id = self.app.cell_manager.setup_cell_id
            self._populate_setup_globals(glbls, setup_id)

            order = dataflow.topological_sort(
                self.app.graph,
                list(self.app.cell_manager.valid_cell_ids()),
            )
            for cid in order:
                if cid == setup_id:
                    # Setup globals were populated above.
                    continue
                if cid not in self._classification.compilable:
                    continue

                if self._should_cancel is not None and self._should_cancel():
                    raise BuildCancelled()

                cell = self.app.graph.cells[cid]
                cell_name = self.app.cell_manager.cell_name(cid)
                # Imported lazily to keep build.py the canonical home
                # for the helper while still surfacing the same label
                # everywhere a runner emits an event.
                from marimo._build.build import display_name

                cell_label = display_name(cell_name, cell)
                if self._progress_callback is not None:
                    self._progress_callback(
                        CellExecuting(
                            cell_id=cid,
                            name=cell_name,
                            display_name=cell_label,
                        )
                    )
                t0 = time.perf_counter()
                with get_context().with_cell_id(cid):
                    try:
                        self._executor.execute_cell(
                            cell, glbls, self.app.graph
                        )
                    except MarimoRuntimeException as e:
                        # Marimo wraps every cell exception in
                        # MarimoRuntimeException, which inherits from
                        # BaseException — catch it explicitly and
                        # surface the underlying error with the cell
                        # name attached.
                        cause = e.__cause__ or e
                        if self._progress_callback is not None:
                            self._progress_callback(
                                CellFailed(
                                    cell_id=cid,
                                    name=cell_name,
                                    display_name=cell_label,
                                    error=f"{type(cause).__name__}: {cause}",
                                )
                            )
                        raise BuildExecutionError(cell_name, cause) from cause

                self.captured_defs[cid] = {
                    name: glbls[name] for name in cell.defs if name in glbls
                }
                if self._progress_callback is not None:
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    self._progress_callback(
                        CellExecuted(
                            cell_id=cid,
                            name=cell_name,
                            display_name=cell_label,
                            elapsed_ms=elapsed_ms,
                        )
                    )

    def _populate_setup_globals(
        self, glbls: dict[str, Any], setup_id: CellId_t
    ) -> None:
        """Make setup-cell defs available to subsequent cells.

        ``App.run()`` relies on the user importing the notebook module,
        which executes ``with app.setup: ...`` as ordinary Python and
        records the resulting locals on ``app._setup._glbls``. Build
        loads notebooks via the IR path (:func:`marimo._ast.load.load_app`),
        which never executes the source — so we must run the setup
        cell body ourselves.
        """
        setup_glbls = (
            self.app._app._setup._glbls
            if self.app._app._setup is not None
            else None
        )
        if setup_glbls:
            glbls.update(setup_glbls)
            return
        setup_cell = self.app.graph.cells.get(setup_id)
        if setup_cell is None:
            return
        with get_context().with_cell_id(setup_id):
            self._executor.execute_cell(setup_cell, glbls, self.app.graph)
