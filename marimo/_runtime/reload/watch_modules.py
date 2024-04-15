# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import itertools
import sys
import threading
import time
from modulefinder import ModuleFinder
from typing import TYPE_CHECKING

from marimo._ast.cell import CellId_t, CellImpl
from marimo._messaging.ops import CellOp
from marimo._messaging.types import Stream
from marimo._runtime import dataflow
from marimo._runtime.reload.autoreload import ModuleReloader

if TYPE_CHECKING:
    import types


def modules_imported_by_cell(cell: CellImpl) -> set[str]:
    modules = set()
    for import_data in cell.imports:
        if import_data.module in sys.modules:
            modules.add(import_data.module)
        if import_data.imported_symbol in sys.modules:
            modules.add(import_data.imported_symbol)
    return modules


def depends_on(
    src_module: types.ModuleType,
    target_filenames: set[str],
    failed_filenames: set[str],
) -> bool:
    if not hasattr(src_module, "__file__") or src_module.__file__ is None:
        return False

    if src_module.__file__ in failed_filenames:
        return False

    finder = ModuleFinder()
    try:
        finder.run_script(src_module.__file__)
    except Exception:
        failed_filenames.add(src_module.__file__)
        return False

    for found_module in itertools.chain([src_module], finder.modules.values()):
        if (
            hasattr(found_module, "__file__")
            and found_module.__file__ in target_filenames
        ):
            return True
    return False


def check_modules(
    modules: dict[str, types.ModuleType],
    reloader: ModuleReloader,
    failed_filenames: set[str],
) -> dict[str, types.ModuleType]:
    stale_modules: dict[str, types.ModuleType] = {}
    modified_modules = reloader.check(modules=sys.modules, reload=False)
    for modname, module in modules.items():
        if depends_on(
            src_module=module,
            target_filenames=set(
                m.__file__ for m in modified_modules if m.__file__ is not None
            ),
            failed_filenames=failed_filenames,
        ):
            stale_modules[modname] = module

    return stale_modules


def watch_modules(
    graph: dataflow.DirectedGraph, should_exit: threading.Event, stream: Stream
) -> None:
    reloader = ModuleReloader()
    failed_filenames: set[str] = set()
    while not should_exit.is_set():
        time.sleep(1)
        # Collect the modules used by each cell
        modules: dict[str, types.ModuleType] = {}
        modname_to_cell_id: dict[str, CellId_t] = {}
        with graph.lock:
            for cell_id, cell in graph.cells.items():
                for modname in modules_imported_by_cell(cell):
                    if modname in sys.modules:
                        modules[modname] = sys.modules[modname]
                        modname_to_cell_id[modname] = cell_id
        # If any modules are stale, communicate that to the FE
        stale_modules = check_modules(
            modules=modules,
            reloader=reloader,
            failed_filenames=failed_filenames,
        )
        if stale_modules:
            stale_cell_ids = [
                modname_to_cell_id[modname] for modname in stale_modules
            ]
            for cid in stale_cell_ids:
                CellOp(cell_id=cid, stale_modules=True).broadcast(
                    stream=stream
                )


class ModuleWatcher:
    def __init__(self, graph: dataflow.DirectedGraph, stream: Stream) -> None:
        self.graph = graph
        self.should_exit = threading.Event()
        self.stream = stream
        self.watcher_thread: threading.Thread | None = None

    def start(self) -> None:
        self.should_exit.clear()
        self.watcher_thread = threading.Thread(
            target=watch_modules,
            args=(self.graph, self.should_exit, self.stream),
            daemon=True,
        )
        self.watcher_thread.start()

    def stop(self) -> None:
        self.should_exit.set()
        self.watcher_thread = None

    def is_running(self) -> bool:
        return self.watcher_thread is not None
