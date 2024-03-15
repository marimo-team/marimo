# Copyright 2024 Marimo. All rights reserved.
import importlib.util
import urllib.request
import subprocess

from marimo._runtime.dataflow import DirectedGraph
from marimo._runtime.packages.module_name_to_pypi_name import (
    MODULE_NAME_TO_PYPI_NAME,
)


class PackageManager:
    """Tracks modules/packages used by a collection of cells

    Most methods operate on module names, not package names, since the main
    purpose of this class is to attempt to install packages that make
    missing modules available.

    Currently specialized to PyPI.
    """
    def __init__(self, graph: DirectedGraph) -> None:
        self.graph = graph
        # modules that do not have corresponding packages on PyPI;
        # no good way to determine whether or not we should exclude a package
        # other than trying to install it ...
        self._excluded_modules: set[str] = set()

    def canonicalize(self, module_name: str) -> str:
        """Canonicalizes a module name to a package name on PyPI."""
        if module_name in MODULE_NAME_TO_PYPI_NAME:
            return MODULE_NAME_TO_PYPI_NAME[module_name]
        else:
            return module_name

    def modules(self) -> set[str]:
        """Modules imported by cells."""
        return set(
            mod
            for cell in self.graph.cells.values()
            for mod in cell.imported_modules
        )

    # UNUSED
    def _on_pypi(self, module: str) -> bool:
        package = self.canonicalize(module)
        response = urllib.request.urlopen(
            f"pypi.org/search?q={package}"
        ).read()
        return "no results" not in response

    def missing_modules(self) -> set[str]:
        """Modules that will fail to import."""
        return set(
            mod
            for mod in self.modules()
            if importlib.util.find_spec(mod) is None
        )

    def missing_packages(self) -> set[str]:
        """Candidate installed packages that cells appear to rely on"""
        return set(
            self.canonicalize(mod)
            for mod in self.missing_modules() - self._excluded_modules
        )

    def install_module(self, module: str) -> bool:
        """Attempt to install a package that makes this module available.

        If installation fails, removes this module from candidate list of
        missing packages.

        Returns True if installation succeeded, else False
        """
        ret = subprocess.run(["pip", "install", self.canonicalize(module)])
        if ret != 0:
            self._excluded_modules.add(module)
            return False
        return True

    def install_missing_packages(self) -> set[str]:
        """Attempt to install packages for all missing modules.

        Returns a set of module names that were installed.
        """
        installed = set()
        missing_modules = self.missing_modules()
        for module in missing_modules - self._excluded_modules:
            if self.install_module(module):
                installed.add(module)
        return installed
