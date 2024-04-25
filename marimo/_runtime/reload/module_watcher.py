# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import itertools
import pathlib
import sys
import threading
import time
from modulefinder import ModuleFinder
from typing import TYPE_CHECKING, Callable, Literal

from marimo._ast.cell import CellId_t, CellImpl
from marimo._messaging.types import Stream
from marimo._runtime import dataflow
from marimo._runtime.reload.autoreload import ModuleReloader

if TYPE_CHECKING:
    import types


def _modules_imported_by_cell(
    cell: CellImpl, sys_modules: dict[str, types.ModuleType]
) -> set[str]:
    """Get the modules imported by a cell"""
    modules = set()
    for import_data in cell.imports:
        if import_data.module in sys_modules:
            modules.add(import_data.module)
        if import_data.imported_symbol in sys_modules:
            # The imported symbol may or may not be a module, which
            # is why we check if it's in sys.modules
            #
            # e.g., from a import b
            #
            # a.b could be a module, but it could also be a function, ...
            modules.add(import_data.imported_symbol)
    return modules


def is_submodule(src_name: str, target_name: str) -> bool:
    """Returns True if src_name is a parent of target_name

    eg: "marimo.plugins" is a parent of "marimo.plugins.ui", returns True
    """
    src_parts = src_name.split(".")
    target_parts = target_name.split(".")
    if len(src_parts) > len(target_parts):
        return False
    return all(src_parts[i] == target_parts[i] for i in range(len(src_parts)))


def _depends_on(
    src_module: types.ModuleType,
    target_modules: set[types.ModuleType],
    failed_filenames: set[str],
    finder: ModuleFinder,
) -> bool:
    """Returns whether src_module depends on any of target_filenames"""
    if not hasattr(src_module, "__file__") or src_module.__file__ is None:
        return False

    if src_module.__file__ in failed_filenames:
        return False

    try:
        finder.run_script(src_module.__file__)
    except SyntaxError:
        # user introduced a syntax error, maybe; still check if the
        # module itself has been modified
        pass
    except Exception:
        # some modules like numpy fail when called with run_script;
        # run_script takes a long time before failing on them, so
        # don't try to analyze them again
        failed_filenames.add(src_module.__file__)
        return False

    target_filenames = set(
        t.__file__ for t in target_modules if hasattr(t, "__file__")
    )
    for found_module in itertools.chain([src_module], finder.modules.values()):
        file = getattr(found_module, "__file__", None)
        if file is None:
            continue

        # easy case: a discovered module was directly modified
        if file in target_filenames:
            return True

        # if a discovered module is a package, check if any of the modified
        # modules are contained in that package
        if file.endswith("__init__.py") and any(
            is_submodule(src_module.__name__, target_module.__name__)
            for target_module in target_modules
        ):
            return True

    return False


def _is_third_party_module(module: types.ModuleType) -> bool:
    filepath = getattr(module, "__file__", None)
    if filepath is None:
        return False
    return "site-packages" in pathlib.Path(filepath).parts


def _get_excluded_modules(modules: dict[str, types.ModuleType]) -> list[str]:
    return [
        modname
        for modname in modules
        if (m := modules.get(modname)) is not None
        and _is_third_party_module(m)
    ]


def _check_modules(
    modules: dict[str, types.ModuleType],
    reloader: ModuleReloader,
    failed_filenames: set[str],
    finder: ModuleFinder,
    sys_modules: dict[str, types.ModuleType],
) -> dict[str, types.ModuleType]:
    """Returns the set of modules used by the graph that have been modified"""
    stale_modules: dict[str, types.ModuleType] = {}
    modified_modules = reloader.check(modules=sys_modules, reload=False)
    # TODO(akshayka): could also exclude modules part of the standard library;
    # haven't found a reliable way to do this, however.
    for modname, module in modules.items():
        if _depends_on(
            src_module=module,
            target_modules=set(m for m in modified_modules if m is not None),
            failed_filenames=failed_filenames,
            finder=finder,
        ):
            stale_modules[modname] = module

    return stale_modules


def watch_modules(
    graph: dataflow.DirectedGraph,
    mode: Literal["detect", "autorun"],
    enqueue_run_stale_cells: Callable[[], None],
    should_exit: threading.Event,
    run_is_processed: threading.Event,
    stream: Stream,
) -> None:
    """Watches for changes to modules used by graph

    The modules used by the graph are determined statically, by analyzing the
    modules imported by the notebook as well as the modules imported by those
    modules, recursively.
    """
    reloader = ModuleReloader()
    # modules that failed to be analyzed
    failed_filenames: set[str] = set()
    # work with a copy to avoid race conditions
    # in CPython, dict.copy() is atomic
    sys_modules = sys.modules.copy()
    finder = ModuleFinder(excludes=_get_excluded_modules(sys_modules))
    while not should_exit.is_set():
        # Collect the modules used by each cell
        modules: dict[str, types.ModuleType] = {}
        modname_to_cell_id: dict[str, CellId_t] = {}
        with graph.lock:
            for cell_id, cell in graph.cells.items():
                for modname in _modules_imported_by_cell(cell, sys_modules):
                    if modname in sys_modules:
                        modules[modname] = sys_modules[modname]
                        modname_to_cell_id[modname] = cell_id
        stale_modules = _check_modules(
            modules=modules,
            reloader=reloader,
            failed_filenames=failed_filenames,
            finder=finder,
            sys_modules=sys_modules,
        )
        if stale_modules:
            with graph.lock:
                # If any modules are stale, communicate that to the FE
                stale_cell_ids = dataflow.transitive_closure(
                    graph,
                    set(
                        modname_to_cell_id[modname]
                        for modname in stale_modules
                    ),
                )
                for cid in stale_cell_ids:
                    graph.cells[cid].set_stale(stale=True, stream=stream)
            if mode == "autorun":
                run_is_processed.clear()
                enqueue_run_stale_cells()
        # Don't proceed until enqueue_run_stale_cells() has been processed,
        # ie until stale cells have been rerun
        run_is_processed.wait()
        time.sleep(1)
        # Update our snapshot of sys.modules
        sys_modules = sys.modules.copy()
        # Update excluded modules in case the module set has changed.
        finder.excludes = _get_excluded_modules(sys_modules)


class ModuleWatcher:
    def __init__(
        self,
        graph: dataflow.DirectedGraph,
        mode: Literal["detect", "autorun"],
        enqueue_run_stale_cells: Callable[[], None],
        stream: Stream,
    ) -> None:
        # ModuleWatcher uses the graph to determine the modules used by the
        # notebook
        self.graph = graph
        # When set, signals the watcher thread to exit
        self.should_exit = threading.Event()
        # When False, an ExecuteStaleRequest is inflight to the kernel
        self.run_is_processed = threading.Event()
        self.run_is_processed.set()
        # To communicate staleness to the FE
        self.stream = stream
        # If autorun, stale cells are automatically scheduled for execution
        self.mode = mode
        # A callable that signals the kernel to run stale cells
        self.enqueue_run_stale_cells = enqueue_run_stale_cells
        threading.Thread(
            target=watch_modules,
            args=(
                self.graph,
                self.mode,
                self.enqueue_run_stale_cells,
                self.should_exit,
                self.run_is_processed,
                self.stream,
            ),
            daemon=True,
        ).start()

    def stop(self) -> None:
        self.should_exit.set()
