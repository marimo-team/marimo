from functools import partial

from marimo._ast import compiler
from marimo._runtime.dataflow import DirectedGraph
from marimo._runtime.packages.module_registry import ModuleRegistry

parse_cell = partial(compiler.compile_cell, cell_id="0")


def test_defining_cell() -> None:
    mgr = ModuleRegistry(graph := DirectedGraph())
    mpl = parse_cell("import matplotlib")
    np = parse_cell("import numpy")
    graph.register_cell("0", mpl)
    graph.register_cell("1", np)
    assert mgr.defining_cell("matplotlib") == "0"
    assert mgr.defining_cell("numpy") == "1"


def test_defining_cell_dotted() -> None:
    mgr = ModuleRegistry(graph := DirectedGraph())
    mpl = parse_cell("import matplotlib.pyplot as plt")
    graph.register_cell("0", mpl)
    assert mgr.defining_cell("matplotlib") == "0"
    assert mgr.defining_cell("pyplot") is None
    assert mgr.defining_cell("plt") is None


def test_missing_modules() -> None:
    mgr = ModuleRegistry(graph := DirectedGraph())
    graph.register_cell("0", parse_cell("import does.nt.exist as foo"))
    graph.register_cell(
        "1", parse_cell("import time; import super_fake_package")
    )
    assert mgr.missing_modules() == set(["does", "super_fake_package"])
