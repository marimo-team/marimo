# Copyright 2026 Marimo. All rights reserved.
"""Autoreload manager: owns `ModuleReloader` and `ModuleWatcher` on behalf of the kernel."""

from __future__ import annotations

import contextlib
import sys
from typing import TYPE_CHECKING, Literal

from marimo._runtime.reload.autoreload import ModuleReloader
from marimo._runtime.reload.module_watcher import ModuleWatcher
from marimo._utils.platform import is_pyodide

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._ast.cell import CellImpl
    from marimo._runtime.runner.hook_context import OnFinishHookContext
    from marimo._runtime.runtime import Kernel

AutoReloadMode = Literal["off", "lazy", "autorun"]


class AutoreloadManager:
    """Owns ModuleReloader + ModuleWatcher and reacts to config changes."""

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self._reloader: ModuleReloader | None = None
        self._watcher: ModuleWatcher | None = None

        # Re-arm the watcher after every kernel run, regardless of trigger.
        kernel._hooks.add_on_finish(self._on_finish_hook)

    @property
    def reloader(self) -> ModuleReloader | None:
        return self._reloader

    @property
    def watcher(self) -> ModuleWatcher | None:
        return self._watcher

    def update_from_config(self, mode: AutoReloadMode) -> None:
        """Start, stop, or swap the watcher/reloader to match `runtime.auto_reload`."""
        # Pyodide doesn't support hot module reloading.
        if (mode == "lazy" or mode == "autorun") and not is_pyodide():
            if self._reloader is None:
                self._reloader = ModuleReloader()

            if self._watcher is not None and self._watcher.mode != mode:
                self._watcher.stop()
                self._watcher = None

            if self._watcher is None:
                self._watcher = ModuleWatcher(
                    self._kernel.graph,
                    reloader=self._reloader,
                    enqueue_run_stale_cells=self._kernel._execute_stale_cells_callback,
                    mode=mode,
                    stream=self._kernel.stream,
                )
        else:
            self._reloader = None
            if self._watcher is not None:
                self._watcher.stop()
                self._watcher = None

    def teardown(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None
        self._reloader = None

    def flag_if_imports_stale(self, cell: CellImpl) -> None:
        reloader = self._reloader
        if reloader is None:
            return
        if reloader.cell_uses_stale_modules(cell):
            self._kernel.graph.set_stale({cell.cell_id}, prune_imports=True)

    @contextlib.contextmanager
    def cell_scope(self) -> Iterator[None]:
        """Reload modified modules on entry; record mtimes for newly-imported modules on exit."""
        if self._reloader is None:
            yield
            return
        snapshot = set(sys.modules)
        self._reloader.check(modules=sys.modules, reload=True)
        try:
            yield
        finally:
            new_modules = set(sys.modules) - snapshot
            self._reloader.check(
                modules={m: sys.modules[m] for m in new_modules},
                reload=False,
            )

    def _on_finish_hook(self, ctx: OnFinishHookContext) -> None:
        del ctx
        if self._watcher is not None:
            self._watcher.run_is_processed.set()
