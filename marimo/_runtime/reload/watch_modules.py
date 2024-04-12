import sys
import time
import types
from modulefinder import ModuleFinder
from marimo._ast.cell import CellId_t

from marimo._messaging.types import Stream
from marimo._runtime import dataflow
from marimo._runtime.reload.autoreload import ModuleReloader


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

    for found_module in finder.modules.values():
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
    graph: dataflow.DirectedGraph,
    stream: Stream,
) -> None:
    reloader = ModuleReloader()
    failed_filenames: set[str] = set()
    while True:
        # Collect the modules used by the graph
        time.sleep(5)
        modules: dict[str, types.ModuleType] = {}
        modname_to_cell_id: dict[str, CellId_t] = {}
        with graph.lock:
            for cell_id, cell in graph.cells.items():
                for modname in cell.imported_modules:
                    if modname in sys.modules:
                        modules[modname] = sys.modules[modname]
                        modname_to_cell_id[modname] = cell_id
        stale_modules = check_modules(
            modules=modules,
            reloader=reloader,
            failed_filenames=failed_filenames,
        )
        if stale_modules:
            stale_cells = [
                modname_to_cell_id[modname] for modname in stale_modules
            ]
            # TODO: tell FE that these cells are stale
