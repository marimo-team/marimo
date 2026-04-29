# Copyright 2026 Marimo. All rights reserved.
"""Persistent in-process runtime for the dataflow API.

`DataflowRuntime` owns a long-lived module + globals dict for one notebook,
runs cells with explicit pruning, and exposes `mo.api.input(...)` UI elements
as remote-controllable inputs.

Lifecycle:
  - First call to `ensure_initialized()` runs every cell with default UI
    element values; this populates globals and builds the input registry.
  - Subsequent calls to `apply_inputs_and_run(...)` push input overrides into
    the existing UI elements (via their `_update` method), prune the graph
    to the cells needed for subscribed variables, and run only those cells.
  - The schema is computed once after initialization and cached.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import sys
import threading
import time
import traceback
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from marimo._dataflow.api import DATAFLOW_INPUT_MARKER, _InputMetadata
from marimo._dataflow.ast_scan import find_all_input_assignments
from marimo._dataflow.protocol import (
    DataflowEvent,
    RunEvent,
    VarErrorEvent,
    VarEvent,
)
from marimo._dataflow.pruning import compute_cells_to_run
from marimo._dataflow.serialize import infer_kind, serialize_value
from marimo._messaging.types import NoopStream
from marimo._runtime.context.types import (
    runtime_context_installed,
)
from marimo._runtime.executor import ExecutionConfig, get_executor
from marimo._runtime.patches import create_main_module

if TYPE_CHECKING:
    from marimo._ast.app import InternalApp
    from marimo._plugins.ui._core.ui_element import UIElement


class DataflowRuntime:
    """Persistent in-process runtime for one notebook.

    Thread-safe at the request level (an `asyncio.Lock` serializes runs).
    """

    def __init__(self, app: InternalApp) -> None:
        self._app = app
        self._initialized = False
        self._init_lock = threading.Lock()
        self._run_lock = asyncio.Lock()
        self._installed_context = False
        self._declared_inputs: dict[str, str] = {}

        self._module = create_main_module(
            file=app.filename,
            input_override=None,
            print_override=None,
            doc=None,
        )
        self._executor = get_executor(ExecutionConfig())

        # Cell execution must happen on a single thread because the marimo
        # runtime context is `threading.local`. Pin all work to a dedicated
        # worker so the script context installed during initialization stays
        # accessible across requests.
        self._worker = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="dataflow-runtime"
        )

    @property
    def globals(self) -> dict[str, Any]:
        return self._module.__dict__

    def get_input_element(self, name: str) -> UIElement[Any, Any] | None:
        """Return the `mo.api.input` UI element bound to `name`, or None."""
        from marimo._plugins.ui._core.ui_element import UIElement

        val = self.globals.get(name)
        if isinstance(val, UIElement) and hasattr(val, DATAFLOW_INPUT_MARKER):
            return val
        return None

    def list_input_elements(self) -> dict[str, UIElement[Any, Any]]:
        """Return {name: ui_element} for every `mo.api.input` element."""
        from marimo._plugins.ui._core.ui_element import UIElement

        out: dict[str, UIElement[Any, Any]] = {}
        for name, val in self.globals.items():
            if isinstance(val, UIElement) and hasattr(
                val, DATAFLOW_INPUT_MARKER
            ):
                out[name] = val
        return out

    def list_input_metadata(self) -> dict[str, _InputMetadata]:
        """Return {name: metadata} for every `mo.api.input` element."""
        return {
            name: getattr(el, DATAFLOW_INPUT_MARKER)
            for name, el in self.list_input_elements().items()
        }

    def close(self) -> None:
        """Tear down the worker and any installed runtime context."""
        if self._installed_context:

            def _teardown() -> None:
                from marimo._runtime.context.types import (
                    runtime_context_installed,
                    teardown_context,
                )

                if runtime_context_installed():
                    teardown_context()

            try:
                self._worker.submit(_teardown).result(timeout=5)
            except Exception:
                pass
            self._installed_context = False
        self._worker.shutdown(wait=False)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def submit_to_worker(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Submit a callable to the runtime's dedicated worker thread.

        Useful for synchronous callers (e.g. tests) that want to invoke
        runtime methods without going through the async API. Ensures any
        runtime context installation happens on the worker thread instead of
        leaking into whatever thread the caller is running on.
        """
        return self._worker.submit(fn, *args, **kwargs).result()

    def ensure_initialized(self) -> None:
        """Run the full graph with default values once (idempotent).

        Always runs on the dedicated worker thread so the script context
        ends up where subsequent cell executions can find it.
        """
        if self._initialized:
            return
        self._worker.submit(self._initialize_blocking).result()

    def _initialize_blocking(self) -> None:
        with self._init_lock:
            if self._initialized:
                return
            self._declared_inputs = find_all_input_assignments(self._app)
            self._install_context()
            self._run_cells(
                list(self._app.execution_order), tolerant=True
            )
            self._initialized = True

    async def apply_inputs_and_run(
        self,
        inputs: dict[str, Any],
        subscribed: set[str],
    ) -> list[DataflowEvent]:
        """Apply input overrides, run only the cells needed for `subscribed`."""
        async with self._run_lock:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._worker,
                self._apply_inputs_and_run_sync,
                inputs,
                subscribed,
            )

    def _apply_inputs_and_run_sync(
        self,
        inputs: dict[str, Any],
        subscribed: set[str],
    ) -> list[DataflowEvent]:
        # We're already running on the dedicated worker thread; call the
        # blocking init directly to avoid deadlocking on our own executor.
        self._initialize_blocking()

        run_id = uuid4().hex[:8]
        events: list[DataflowEvent] = [
            RunEvent(run_id=run_id, status="started")
        ]
        start = time.time()

        applied_inputs = self._apply_overrides(inputs, run_id, events)

        try:
            cells_to_run = list(
                compute_cells_to_run(
                    graph=self._app.graph,
                    inputs=applied_inputs,
                    subscribed=subscribed,
                    changed_inputs=set(applied_inputs.keys()) or None,
                )
            )
            # An `mo.api.input` UI element is a *singleton* across the
            # session: it's created once during initialization, lives in
            # globals, and is mutated in place via `_update`. Re-running its
            # declaring cell would create a fresh element that throws away
            # any override the client has applied. So we always exclude
            # input-declaring cells from re-runs.
            input_cells = set(self._declared_inputs.values())
            cells_to_run = [c for c in cells_to_run if c not in input_cells]
            self._run_cells(cells_to_run)
        except Exception as e:
            tb = traceback.format_exc()
            for name in sorted(subscribed):
                events.append(
                    VarErrorEvent(
                        name=name,
                        run_id=run_id,
                        error=str(e),
                        traceback=tb,
                    )
                )
            events.append(
                RunEvent(
                    run_id=run_id,
                    status="done",
                    elapsed_ms=(time.time() - start) * 1000,
                )
            )
            return events

        seq = 0
        for name in sorted(subscribed):
            seq += 1
            if name in self.globals:
                events.append(
                    self._make_var_event(name, run_id, seq)
                )
            else:
                events.append(
                    VarErrorEvent(
                        name=name,
                        run_id=run_id,
                        error=(
                            f"Variable '{name}' was not produced by the graph"
                        ),
                    )
                )

        events.append(
            RunEvent(
                run_id=run_id,
                status="done",
                elapsed_ms=(time.time() - start) * 1000,
            )
        )
        return events

    def _apply_overrides(
        self,
        inputs: dict[str, Any],
        run_id: str,
        events: list[DataflowEvent],
    ) -> dict[str, Any]:
        """Push input overrides into the existing UI elements (or globals).

        Returns the dict of inputs that were successfully applied. Failures
        are surfaced via VarErrorEvents on the events list.
        """
        applied: dict[str, Any] = {}
        for name, value in inputs.items():
            element = self.get_input_element(name)
            if element is not None:
                try:
                    element._update(value)
                except Exception as e:
                    events.append(
                        VarErrorEvent(
                            name=name,
                            run_id=run_id,
                            error=f"failed to apply input {name}: {e}",
                        )
                    )
                    continue
            else:
                self.globals[name] = value
            applied[name] = value
        return applied

    def _make_var_event(
        self, name: str, run_id: str, seq: int
    ) -> VarEvent:
        from marimo._plugins.ui._core.ui_element import UIElement

        value = self.globals[name]
        if isinstance(value, UIElement):
            value = value.value
        kind = infer_kind(value)
        json_value, ref = serialize_value(value, encoding="json")
        return VarEvent(
            name=name,
            kind=kind,
            encoding="json",
            run_id=run_id,
            seq=seq,
            value=json_value,
            ref=ref,
        )

    def _install_context(self) -> None:
        from marimo._runtime.context.script_context import (
            initialize_script_context,
        )

        if not runtime_context_installed():
            initialize_script_context(
                app=self._app,
                stream=NoopStream(),
                filename=self._app.filename,
            )
            self._installed_context = True

        from marimo._output.formatters.formatters import register_formatters
        from marimo._output.formatting import FORMATTERS

        if not FORMATTERS.is_empty():
            register_formatters()

    def _run_cells(
        self, cells: list[Any], *, tolerant: bool = False
    ) -> None:
        """Run the given cells in order against the persistent globals.

        When `tolerant` is True (used during default-state initialization),
        per-cell exceptions are swallowed so cells with unresolved free
        variables don't block schema introspection. When False (used during
        client-driven runs), exceptions are re-raised so the dataflow API
        can surface them to the caller.
        """
        from marimo._ast.names import SETUP_CELL_NAME
        from marimo._runtime.context.types import get_context
        from marimo._runtime.exceptions import MarimoRuntimeException
        from marimo._types.ids import CellId_t

        graph = self._app.graph
        glbls = self.globals

        with _patched_main(self._module):
            for cid in cells:
                if cid == CellId_t(SETUP_CELL_NAME):
                    continue
                if graph.is_disabled(cid):
                    continue
                cell = graph.cells.get(cid)
                if cell is None:
                    continue
                with get_context().with_cell_id(cid):
                    try:
                        self._executor.execute_cell(cell, glbls, graph)
                    except MarimoRuntimeException as e:
                        if tolerant:
                            continue
                        cause = e.__cause__
                        if cause is not None:
                            raise cause from None
                        raise
                    except Exception:
                        if tolerant:
                            continue
                        raise


@contextlib.contextmanager
def _patched_main(module: Any) -> Any:
    """Briefly install `module` as `sys.modules["__main__"]`.

    This makes `if __name__ == "__main__"` and pickle work as cells expect.
    Scoped narrowly to cell execution so we don't leak across requests.
    """
    main = sys.modules["__main__"]
    sys.modules["__main__"] = module
    try:
        yield module
    finally:
        sys.modules["__main__"] = main
