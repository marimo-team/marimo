# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from marimo._ast.names import SETUP_CELL_NAME
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.types import NoopStream
from marimo._runtime import dataflow
from marimo._runtime.app.common import RunOutput
from marimo._runtime.context.types import (
    get_context,
    initialize_context,
    runtime_context_installed,
    safe_get_context,
    teardown_context,
)
from marimo._runtime.control_flow import MarimoStopError
from marimo._runtime.exceptions import (
    MarimoMissingRefError,
    MarimoRescheduleError,
    MarimoRuntimeException,
    unwrap_user_exception,
)
from marimo._runtime.executor import (
    Evaluator,
    resolve_executor,
)
from marimo._runtime.patches import (
    create_main_module,
    extract_docstring_from_header,
    patch_main_module_context,
)
from marimo._runtime.runner.result import RunResult
from marimo._runtime.runner.scheduler import SequentialScheduler
from marimo._types.ids import CellId_t
from marimo._utils.asyncio_utils import run_coroutine_blocking

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._ast.app import InternalApp
    from marimo._runtime.context.types import RuntimeContext
    from marimo._save.cache import CacheState


class AppScriptRunner:
    """Runs an app in a script context."""

    def __init__(
        self,
        app: InternalApp,
        filename: str | None,
        glbls: dict[str, Any] | None = None,
    ) -> None:
        self.app = app
        self.filename = filename
        self._docstring = extract_docstring_from_header(app._app._header)
        self._glbls = glbls if glbls else {}
        # `glbls` also carries the setup cell's own values; any other name
        # is a `defs` override.
        # The setup cell's id carries a prefix when the notebook is imported
        # from inside another notebook, so it is looked up by its real id.
        setup_cell = self.app.graph.cells.get(
            self.app.cell_manager.setup_cell_id
        )
        setup_defs = setup_cell.defs if setup_cell is not None else set()
        self._has_overrides = bool(self._glbls.keys() - setup_defs)

        # Setup cell cannot be overridden, and it's possible that some
        # variables are not defined, so ignore it.
        pruned_execution_order = dataflow.prune_cells_for_overrides(
            self.app.graph,
            self.app.execution_order,
            self._glbls,
            excluded=CellId_t(SETUP_CELL_NAME),
        )

        cells_to_run = [
            cid
            for cid in pruned_execution_order
            if app.cell_manager.cell_data_at(cid).cell is not None
            and not self.app.graph.is_disabled(cid)
        ]

        self._scheduler = SequentialScheduler(cells_to_run, self.app.graph)
        self._evaluator = Evaluator(executor=resolve_executor(), lifecycles=[])

    # _run_synchronous and _run_asynchronous are deliberate near-twins:
    # the only difference is the await on the cell step. Keeping them
    # as separate methods (rather than driving an event loop
    # unconditionally) preserves the no-event-loop guarantee for purely
    # synchronous apps.
    def _run_synchronous(
        self,
        post_execute_hooks: list[Callable[[], Any]],
    ) -> RunOutput:
        with patch_main_module_context(
            create_main_module(
                file=self.filename,
                input_override=None,
                doc=self._docstring,
            )
        ) as module:
            glbls = module.__dict__
            glbls.update(self._glbls)

            outputs: dict[CellId_t, Any] = {}
            while self._scheduler.pending():
                cid = self._scheduler.pop_cell()
                if self._scheduler.cancelled(cid):
                    continue
                # Setup has already run by this point.
                if cid == CellId_t(SETUP_CELL_NAME):
                    for hook in post_execute_hooks:
                        hook()
                    continue
                cell = self.app.graph.cells[cid]
                with get_context().with_cell_id(cid):
                    try:
                        result = self._evaluator.evaluate_sync(cell, glbls)
                        self._handle_run_result(cid, result, outputs)
                    finally:
                        for hook in post_execute_hooks:
                            hook()
        return outputs, glbls

    async def _run_asynchronous(
        self,
        post_execute_hooks: list[Callable[[], Any]],
    ) -> RunOutput:
        with patch_main_module_context(
            create_main_module(
                file=self.filename,
                input_override=None,
                doc=self._docstring,
            )
        ) as module:
            glbls = module.__dict__
            glbls.update(self._glbls)

            outputs: dict[CellId_t, Any] = {}
            while self._scheduler.pending():
                cid = self._scheduler.pop_cell()
                if self._scheduler.cancelled(cid):
                    continue
                # Setup has already run by this point.
                if cid == CellId_t(SETUP_CELL_NAME):
                    for hook in post_execute_hooks:
                        hook()
                    continue
                cell = self.app.graph.cells[cid]
                with get_context().with_cell_id(cid):
                    try:
                        result = await self._evaluator.evaluate(cell, glbls)
                        self._handle_run_result(cid, result, outputs)
                    finally:
                        for hook in post_execute_hooks:
                            hook()
        return outputs, glbls

    async def _run_asynchronous_in_context(
        self,
        context: RuntimeContext,
        post_execute_hooks: list[Callable[[], Any]],
    ) -> RunOutput:
        """Run the app's cells asynchronously under `context`.

        The runtime context is thread-local. If the awaiting thread has no
        context installed, `context` is installed for the duration of the run
        and torn down afterwards; a thread that already has one is left
        untouched. This makes the coroutine safe to await on a thread other
        than the one `context` was created on.
        """
        installed_context = False
        if not runtime_context_installed():
            initialize_context(context)
            installed_context = True
        try:
            return await self._run_asynchronous(
                post_execute_hooks=post_execute_hooks,
            )
        finally:
            if installed_context:
                teardown_context()

    def _handle_run_result(
        self,
        cid: CellId_t,
        result: RunResult,
        outputs: dict[CellId_t, Any],
    ) -> None:
        """Classify the Evaluator's RunResult; record output/cancel/raise."""
        exc = result.exception
        if exc is None:
            outputs[cid] = result.output
            return
        if isinstance(exc, MarimoRescheduleError):
            # Stale-cache signal from a lifecycle; `cells_to_rerun` includes
            # this cell, so requeueing (producers first) retries it live.
            self._scheduler.requeue_for_rerun(exc.cells_to_rerun)
            return
        if not isinstance(exc, BaseException):
            # Defensive check descendants, since all exceptions are expected to
            # be wrapper..
            outputs[cid] = result.output
            self._scheduler.cancel(cid)
            return
        if isinstance(exc, MarimoRuntimeException):
            unwrapped = unwrap_user_exception(exc, self.app.graph)
            if isinstance(unwrapped, MarimoStopError):
                outputs[cid] = unwrapped.output
                self._scheduler.cancel(cid)
                return
            if isinstance(unwrapped, MarimoMissingRefError):
                name_err = unwrapped.name_error
                raise (
                    name_err if name_err is not None else unwrapped
                ) from None
        raise exc

    def run(self) -> RunOutput:
        from marimo._runtime.context.script_context import (
            initialize_script_context,
        )

        app = self.app

        is_async = False
        for cell in app.cell_manager.cells():
            if cell is None:
                raise RuntimeError(
                    "Unparsable cell encountered. This is a bug in marimo, "
                    "please raise an issue."
                )

            if cell._is_coroutine:
                is_async = True
                break

        installed_script_context = False
        cache: CacheState | None = None
        outer_hash_memo: dict[str, bytes] = {}
        try:
            if not runtime_context_installed():
                # script context is ephemeral, only installed while the app is
                # running
                initialize_script_context(
                    app=app, stream=NoopStream(), filename=self.filename
                )
                installed_script_context = True

            # Content hashes are memoized by variable name. A run started
            # from inside a running notebook reuses that notebook's context,
            # so without a memo of its own it would read the hashes of
            # another notebook's variables of the same name.
            cache = get_context().cache
            outer_hash_memo, cache.hash_memo = cache.hash_memo, {}

            # formatters aren't automatically registered when running as a
            # script
            from marimo._output.formatters.formatters import (
                register_formatters,
            )
            from marimo._output.formatting import FORMATTERS

            if not FORMATTERS.is_empty():
                register_formatters()

            # NB. attached here rather than __init__: config resolution
            # needs the runtime context, and the notebook's inline
            # [tool.marimo.runtime] table merges by filename.
            runtime_config = get_context().marimo_config.get("runtime", {})
            # A cache key can hash the code of the cells that define a ref
            # instead of its value, so with overrides a run would restore,
            # and save, results under the keys of the cells they replace.
            if (
                runtime_config.get("cache_cells", False)
                and not self._has_overrides
            ):
                from marimo._runtime.executor.lifecycles.cached import (
                    CachedLifecycle,
                )

                self._evaluator.lifecycles = [
                    CachedLifecycle(
                        self.app.graph,
                        pin_modules=bool(
                            runtime_config.get("pin_modules", True)
                        ),
                    )
                ]

            post_execute_hooks: list[Callable[[], Any]] = []
            if DependencyManager.matplotlib.has():
                from marimo._output.mpl import close_figures

                post_execute_hooks.append(close_figures)

            if is_async:
                outputs, defs = run_coroutine_blocking(
                    self._run_asynchronous_in_context(
                        get_context(),
                        post_execute_hooks=post_execute_hooks,
                    )
                )
            else:
                outputs, defs = self._run_synchronous(
                    post_execute_hooks=post_execute_hooks,
                )
            return outputs, defs

        # Raise the wrapped user exception from "None" so the stack
        # trace points at the failing cell, not the runner.
        except MarimoRuntimeException as e:
            raise e.__cause__ from None  # type: ignore
        finally:
            from marimo._save.loaders import flush_active_caches
            from marimo._save.manifest import flush_dirty_manifests

            # NB. joins background blob writes; without this, cache entries
            # can drop at interpreter exit.
            flush_active_caches()
            # A script has no kernel run to finish, so nothing else writes
            # the manifest of the entries this run recorded.
            if (context := safe_get_context()) is not None:
                flush_dirty_manifests(context)
            if cache is not None:
                cache.hash_memo = outer_hash_memo
            if installed_script_context:
                teardown_context()
