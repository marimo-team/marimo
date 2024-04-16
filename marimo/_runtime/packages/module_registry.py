# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import importlib.util
import sys

from marimo._ast.cell import CellId_t
from marimo._runtime.dataflow import DirectedGraph


def _is_module_installed(module_name: str) -> bool:
    # importlib.util.find_spec retrieves a module's ModuleSpec, which
    # is typically available as a dunder attribute on the module, i.e.
    # module.__spec__. However, some packages are non-compliant and don't
    # include a __spec__ attr (e.g., manim-slides), which can cause find_spec
    # to throw if the module has already been imported.
    #
    # We don't actually need the spec, we just need to see if a package is
    # available, so we first check if the module is in sys.modules without
    # checking for a __spec__ attr.
    return (
        module_name in sys.modules
        or importlib.util.find_spec(module_name) is not None
    )


class ModuleRegistry:
    def __init__(
        self, graph: DirectedGraph, excluded_modules: set[str] | None = None
    ) -> None:
        self.graph = graph
        # modules that do not have corresponding packages on package index
        self.excluded_modules = (
            excluded_modules if excluded_modules is not None else set()
        )

    def defining_cell(self, module_name: str) -> CellId_t | None:
        """Get the cell id of the cell importing module_name"""
        for cell_id, cell in self.graph.cells.items():
            if cell.namespace_to_variable(module_name) is not None:
                return cell_id
        return None

    def modules(self) -> set[str]:
        """Modules imported by cells."""
        return set(
            mod
            for cell in self.graph.cells.values()
            for mod in cell.imported_namespaces
        )

    def missing_modules(self) -> set[str]:
        """Modules that will fail to import."""
        return (
            set(mod for mod in self.modules() if not _is_module_installed(mod))
            - self.excluded_modules
        )
