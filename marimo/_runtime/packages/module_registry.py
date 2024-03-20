# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import importlib.util

from marimo._ast.cell import CellId_t
from marimo._runtime.dataflow import DirectedGraph


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
            if cell.module_to_variable(module_name) is not None:
                return cell_id
        return None

    def modules(self) -> set[str]:
        """Modules imported by cells."""
        return set(
            mod
            for cell in self.graph.cells.values()
            for mod in cell.imported_modules
        )

    def missing_modules(self) -> set[str]:
        """Modules that will fail to import."""
        return (
            set(
                mod
                for mod in self.modules()
                if importlib.util.find_spec(mod) is None
            )
            - self.excluded_modules
        )
