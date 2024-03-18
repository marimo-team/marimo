# Copyright 2024 Marimo. All rights reserved.
import importlib.util
import os
import subprocess
import sys
import urllib.request

from marimo._ast.cell import CellId_t
from marimo._runtime.dataflow import DirectedGraph
from marimo._runtime.packages.module_name_to_pypi_name import (
    MODULE_NAME_TO_PYPI_NAME,
)
from marimo._utils.platform import is_pyodide


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
        self._package_to_module = {
            v: k for k, v in MODULE_NAME_TO_PYPI_NAME.items()
        }

    def module_to_package(self, module_name: str) -> str:
        """Canonicalizes a module name to a package name on PyPI."""
        if module_name in MODULE_NAME_TO_PYPI_NAME:
            return MODULE_NAME_TO_PYPI_NAME[module_name]
        else:
            return module_name

    def package_to_module(self, package_name: str) -> str:
        """Canonicalizes a package name to a module name."""
        return (
            self._package_to_module[package_name]
            if package_name in self._package_to_module
            else package_name
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

    # UNUSED
    def _on_pypi(self, module: str) -> bool:
        package = self.module_to_package(module)
        response = urllib.request.urlopen(
            f"pypi.org/search?q={package}"
        ).read()
        return "no results" not in response

    def missing_modules(self) -> set[str]:
        """Modules that will fail to import

        Excludes modules that failed to install  from PyPI
        """
        return (
            set(
                mod
                for mod in self.modules()
                if importlib.util.find_spec(mod) is None
            )
            - self._excluded_modules
        )

    def missing_packages(self) -> set[str]:
        """Candidate installed packages that cells appear to rely on"""
        return set(
            self.module_to_package(mod) for mod in self.missing_modules()
        )

    def install_module(self, module: str) -> bool:
        """Attempt to install a package that makes this module available.

        If installation fails, removes this module from candidate list of
        missing packages.

        Returns True if installation succeeded, else False
        """
        completed_process = subprocess.run(
            ["pip", "install", self.module_to_package(module)]
        )
        if completed_process.returncode != 0:
            self._excluded_modules.add(module)
            return False
        return True

    @staticmethod
    def in_virtual_environment() -> bool:
        """Returns True if a venv/virtualenv is activated"""
        # https://stackoverflow.com/questions/1871549/how-to-determine-if-python-is-running-inside-a-virtualenv/40099080#40099080  # noqa: E501
        base_prefix = (
            getattr(sys, "base_prefix", None)
            or getattr(sys, "real_prefix", None)
            or sys.prefix
        )
        return sys.prefix != base_prefix

    @staticmethod
    def in_conda_env() -> bool:
        return "CONDA_DEFAULT_ENV" in os.environ

    @staticmethod
    def is_python_isolated() -> bool:
        """Returns True if not using system Python"""
        return (
            PackageManager.in_virtual_environment()
            or PackageManager.in_conda_env()
            or is_pyodide()
        )
