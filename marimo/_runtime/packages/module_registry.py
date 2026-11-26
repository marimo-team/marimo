# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import importlib.util
import sys
from typing import Literal

from marimo import _loggers
from marimo._runtime.dataflow.topology import GraphTopology
from marimo._runtime.packages.utils import (
    import_lookup_names,
    is_namespace_root,
    is_same_or_submodule,
)
from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


def _is_top_level_installed(module_name: str) -> bool:
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


def _module_kind(name: str) -> Literal["missing", "namespace", "regular"]:
    if (module := sys.modules.get(name)) is not None:
        is_namespace = module.__file__ is None and hasattr(module, "__path__")
        return "namespace" if is_namespace else "regular"
    if (spec := importlib.util.find_spec(name)) is None:
        return "missing"
    is_namespace = (
        spec.origin is None and spec.submodule_search_locations is not None
    )
    return "namespace" if is_namespace else "regular"


def _is_module_installed(module_name: str) -> bool:
    if not is_namespace_root(module_name):
        return _is_top_level_installed(module_name.split(".", maxsplit=1)[0])

    # Looking up a submodule imports its parents; namespace packages have no
    # __init__ to execute.
    parts = module_name.split(".")
    for depth in range(1, len(parts) + 1):
        kind = _module_kind(".".join(parts[:depth]))
        if kind == "missing":
            return False
        if kind == "regular":
            return True
    return True


def _excludes(excluded: str, module_name: str) -> bool:
    # A namespace root is not a package, so excluding it says nothing about
    # the packages under it
    if is_namespace_root(excluded) and "." not in excluded:
        return module_name == excluded
    return is_same_or_submodule(module_name, excluded)


class ModuleRegistry:
    def __init__(
        self, graph: GraphTopology, excluded_modules: set[str] | None = None
    ) -> None:
        self.graph = graph
        # modules that do not have corresponding packages on package index
        self.excluded_modules: set[str] = (
            excluded_modules if excluded_modules is not None else set()
        )

    def defining_cell(self, module_name: str) -> CellId_t | None:
        """Get the cell id of the cell importing module_name"""
        for cell_id, cell in self.graph.cells.items():
            if any(
                is_same_or_submodule(imported, module_name)
                for imported in cell.imported_modules
            ):
                return cell_id
        return None

    def modules(self) -> set[str]:
        """Modules imported by cells."""
        return import_lookup_names(
            mod
            for cell in self.graph.cells.values()
            for mod in cell.imported_modules
        )

    def missing_modules(self) -> set[str]:
        """Modules that will fail to import."""
        return {mod for mod in self.modules() if self._is_missing(mod)}

    def _is_missing(self, module_name: str) -> bool:
        if self._is_excluded(module_name):
            return False
        try:
            return not _is_module_installed(module_name)
        except Exception:
            # Suggestions are best-effort; a broken lookup must not break
            # running or editing cells
            LOGGER.debug(
                "Could not tell if %s is installed", module_name, exc_info=True
            )
            return False

    def _is_excluded(self, module_name: str) -> bool:
        return any(
            _excludes(excluded, module_name)
            for excluded in self.excluded_modules
        )
