# Copyright 2024 Marimo. All rights reserved.
import importlib.util
import subprocess

from marimo._ast.cell import CellImpl
from marimo._runtime.module_name_to_pypi_name import MODULE_NAME_TO_PYPI_NAME


def canonicalize_module_name_to_pypi(module_name: str) -> str:
    if module_name in MODULE_NAME_TO_PYPI_NAME:
        return MODULE_NAME_TO_PYPI_NAME[module_name]
    else:
        return module_name


def missing_packages(cell: CellImpl) -> set[str]:
    return set(
        mod
        for mod in cell.imported_modules
        if importlib.util.find_spec(mod) is None
    )


# don't call in run mode!!
def install(package_name: str) -> None:
    subprocess.run(["pip", "install", package_name])
