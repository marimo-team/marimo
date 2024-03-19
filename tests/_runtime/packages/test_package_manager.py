from functools import partial

from marimo._ast import compiler
from marimo._runtime.dataflow import DirectedGraph
from marimo._runtime.packages.package_manager import PackageManager

parse_cell = partial(compiler.compile_cell, cell_id="0")


def test_module_to_package() -> None:
    mgr = PackageManager(DirectedGraph())
    assert mgr.module_to_package("marimo") == "marimo"
    assert mgr.module_to_package("123_456_789") == "123-456-789"
    assert mgr.module_to_package("sklearn") == "scikit-learn"


def test_package_to_module() -> None:
    mgr = PackageManager(DirectedGraph())
    assert mgr.package_to_module("marimo") == "marimo"
    assert mgr.package_to_module("123-456-789") == "123_456_789"
    assert mgr.package_to_module("scikit-learn") == "sklearn"


def test_defining_cell() -> None:
    mgr = PackageManager(graph := DirectedGraph())
    mpl = parse_cell("import matplotlib")
    np = parse_cell("import numpy")
    graph.register_cell("0", mpl)
    graph.register_cell("1", np)
    assert mgr.defining_cell("matplotlib") == "0"
    assert mgr.defining_cell("numpy") == "1"


def test_defining_cell_dotted() -> None:
    mgr = PackageManager(graph := DirectedGraph())
    mpl = parse_cell("import matplotlib.pyplot as plt")
    graph.register_cell("0", mpl)
    assert mgr.defining_cell("matplotlib") == "0"
    assert mgr.defining_cell("pyplot") is None
    assert mgr.defining_cell("plt") is None


def test_missing_modules() -> None:
    mgr = PackageManager(graph := DirectedGraph())
    graph.register_cell("0", parse_cell("import does.nt.exist as foo"))
    graph.register_cell(
        "1", parse_cell("import time; import super_fake_package")
    )
    assert mgr.missing_modules() == set(["does", "super_fake_package"])
    assert mgr.missing_packages() == set(["does", "super-fake-package"])


def test_missing_module_excluded_after_failed_install() -> None:
    mgr = PackageManager(graph := DirectedGraph())
    # almost surely does not exist
    graph.register_cell("0", parse_cell("import asdfasdfasdfasdfqwerty"))
    assert mgr.missing_packages() == set(["asdfasdfasdfasdfqwerty"])
    mgr.install_module("asdfasdfasdfasdfqwerty")
    # package should be removed from missing_packages if it failed to
    # install -- shouldn't try to reinstall packages that weren't
    # found on the index
    assert not mgr.missing_packages()


def test_is_python_isolated() -> None:
    mgr = PackageManager(DirectedGraph())
    # tests should always be run in an isolated (non-system) environment;
    # we only run them in a virtualenv, venv, or conda env ...
    assert mgr.is_python_isolated()
