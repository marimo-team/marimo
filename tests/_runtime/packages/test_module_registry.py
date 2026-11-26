import sys
from collections.abc import Iterator
from functools import partial
from pathlib import Path

import pytest

from marimo._ast import compiler
from marimo._runtime.dataflow import DirectedGraph
from marimo._runtime.packages import module_registry, utils
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
    assert mgr.defining_cell("matplotlib.pyplot") == "0"
    assert mgr.defining_cell("pyplot") is None
    assert mgr.defining_cell("plt") is None


def test_defining_cell_from_import() -> None:
    mgr = ModuleRegistry(graph := DirectedGraph())
    graph.register_cell("0", parse_cell("from azure import identity"))
    assert mgr.defining_cell("azure.identity") == "0"
    assert mgr.defining_cell("azure") == "0"
    assert mgr.defining_cell("azure.storage") is None


def test_missing_modules() -> None:
    mgr = ModuleRegistry(graph := DirectedGraph())
    graph.register_cell("0", parse_cell("import does.nt.exist as foo"))
    graph.register_cell(
        "1", parse_cell("import time; import super_fake_package")
    )
    assert mgr.missing_modules() == {"does", "super_fake_package"}


def test_relative_imports_are_not_missing() -> None:
    mgr = ModuleRegistry(graph := DirectedGraph())
    graph.register_cell("0", parse_cell("from . import sibling"))
    graph.register_cell("1", parse_cell("from .local_module import thing"))
    assert mgr.modules() == set()


def test_missing_modules_does_not_import_regular_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg = tmp_path / "registry_regular_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("raise RuntimeError('imported')\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    mgr = ModuleRegistry(graph := DirectedGraph())
    graph.register_cell(
        "0", parse_cell("from registry_regular_pkg.sub import thing")
    )
    assert mgr.missing_modules() == set()
    assert "registry_regular_pkg" not in sys.modules


def test_missing_modules_ignores_submodules_of_local_namespace_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "registry_local_dir").mkdir()
    monkeypatch.syspath_prepend(str(tmp_path))

    mgr = ModuleRegistry(graph := DirectedGraph())
    graph.register_cell(
        "0", parse_cell("from registry_local_dir import written_by_a_cell")
    )
    assert mgr.missing_modules() == set()


@pytest.fixture
def namespace_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    """A namespace root with one regular package and a nested namespace."""
    root = "registry_ns"
    (tmp_path / root / "core").mkdir(parents=True)
    (tmp_path / root / "core" / "__init__.py").touch()
    (tmp_path / root / "storage" / "queue").mkdir(parents=True)
    (tmp_path / root / "storage" / "queue" / "__init__.py").touch()
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(utils, "NAMESPACE_PACKAGE_ROOTS", frozenset({root}))
    yield root
    for name in [m for m in sys.modules if m.split(".")[0] == root]:
        del sys.modules[name]


def test_missing_modules_searches_namespace_roots(namespace_root: str) -> None:
    mgr = ModuleRegistry(graph := DirectedGraph())
    graph.register_cell(
        "0",
        parse_cell(
            f"import {namespace_root}.core.exceptions\n"
            f"import {namespace_root}.storage.queue.aio\n"
            f"import {namespace_root}.storage.blob\n"
            f"from {namespace_root} import identity\n"
        ),
    )
    assert mgr.missing_modules() == {
        f"{namespace_root}.storage.blob",
        f"{namespace_root}.identity",
    }


def test_excluding_namespace_root_keeps_its_packages(
    namespace_root: str,
) -> None:
    graph = DirectedGraph()
    graph.register_cell(
        "0", parse_cell(f"import {namespace_root}.storage.blob")
    )
    mgr = ModuleRegistry(graph, excluded_modules={namespace_root})
    assert mgr.missing_modules() == {f"{namespace_root}.storage.blob"}

    mgr = ModuleRegistry(
        graph, excluded_modules={f"{namespace_root}.storage.blob"}
    )
    assert mgr.missing_modules() == set()


def test_failed_lookup_is_not_reported_missing(
    namespace_root: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_lookup(name: str) -> None:
        raise RuntimeError(name)

    monkeypatch.setattr(module_registry, "_module_kind", broken_lookup)
    mgr = ModuleRegistry(graph := DirectedGraph())
    graph.register_cell("0", parse_cell(f"import {namespace_root}.identity"))
    assert mgr.missing_modules() == set()
