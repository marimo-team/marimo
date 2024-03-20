from functools import partial

from marimo._ast import compiler
from marimo._runtime.packages.pypi_package_manager import PipPackageManager

parse_cell = partial(compiler.compile_cell, cell_id="0")


def test_module_to_package() -> None:
    mgr = PipPackageManager()
    assert mgr.module_to_package("marimo") == "marimo"
    assert mgr.module_to_package("123_456_789") == "123-456-789"
    assert mgr.module_to_package("sklearn") == "scikit-learn"


def test_package_to_module() -> None:
    mgr = PipPackageManager()
    assert mgr.package_to_module("marimo") == "marimo"
    assert mgr.package_to_module("123-456-789") == "123_456_789"
    assert mgr.package_to_module("scikit-learn") == "sklearn"


async def test_failed_install_returns_false() -> None:
    mgr = PipPackageManager()
    # almost surely does not exist
    assert not await mgr.install("asdfasdfasdfasdfqwerty")
