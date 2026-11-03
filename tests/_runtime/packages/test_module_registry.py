from functools import partial
from pathlib import Path

import pytest

from marimo._ast import compiler
from marimo._runtime.dataflow import DirectedGraph
from marimo._runtime.packages.module_registry import (
    ModuleRegistry,
    _is_module_installed,
)

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
    assert mgr.defining_cell("matplotlib.pyplot") == "0"
    assert mgr.defining_cell("pyplot") is None
    assert mgr.defining_cell("plt") is None


def test_missing_modules() -> None:
    mgr = ModuleRegistry(graph := DirectedGraph())
    graph.register_cell("0", parse_cell("import does.nt.exist as foo"))
    graph.register_cell(
        "1", parse_cell("import time; import super_fake_package")
    )
    # Full dotted names are kept, so that nested modules can be resolved
    # to their own package instead of their top-level namespace's.
    assert mgr.missing_modules() == {"does.nt.exist", "super_fake_package"}


def test_missing_modules_installed_parent() -> None:
    mgr = ModuleRegistry(graph := DirectedGraph())
    graph.register_cell("0", parse_cell("import json.decoder"))
    graph.register_cell("1", parse_cell("import json.fake_submodule"))
    # json.decoder is installed; json.fake_submodule is not, even though
    # its parent package is.
    assert mgr.missing_modules() == {"json.fake_submodule"}


def test_defining_cell_submodule() -> None:
    mgr = ModuleRegistry(graph := DirectedGraph())
    graph.register_cell("0", parse_cell("import json.decoder.aio"))
    # Installing the package for json.decoder must find the cell that
    # imports a submodule of it, and the missing .aio submodule must be
    # reported even though its parents are installed.
    assert mgr.defining_cell("json.decoder") == "0"
    assert mgr.missing_modules() == {"json.decoder.aio"}


def test_missing_modules_excluded_prefix() -> None:
    graph = DirectedGraph()
    graph.register_cell("0", parse_cell("import pkg.child"))
    mgr = ModuleRegistry(graph, excluded_modules={"pkg"})
    # Excluding a module excludes its submodules too.
    assert mgr.missing_modules() == set()


def test_is_module_installed_broken_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg = tmp_path / "brokenpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("import nonexistent_dep_xyz\n")
    (pkg / "sub.py").write_text("X = 1\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    # brokenpkg is installed, but its own imports are broken; that error
    # must surface instead of reporting brokenpkg.sub as missing.
    with pytest.raises(ModuleNotFoundError) as excinfo:
        _is_module_installed("brokenpkg.sub")
    assert excinfo.value.name == "nonexistent_dep_xyz"
    # A genuinely missing parent still reads as missing.
    assert not _is_module_installed("does.nt.exist")
