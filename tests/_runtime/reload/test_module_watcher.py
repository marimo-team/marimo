from __future__ import annotations

import asyncio
import copy
import pathlib
import sys
import textwrap
from queue import Queue

import pytest
from reload_test_utils import random_modname, update_file

from marimo._config.config import DEFAULT_CONFIG
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.requests import SetUserConfigRequest
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


# these tests use random filenames for modules because they share
# the same sys.modules object, and each test needs fresh modules
async def test_reload_function(
    tmp_path: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
):
    k = execution_kernel
    sys.path.append(str(tmp_path))
    py_file = tmp_path / pathlib.Path(py_modname + ".py")
    py_file.write_text(
        textwrap.dedent(
            """
            def foo():
                return 1
            """
        )
    )

    config = copy.deepcopy(DEFAULT_CONFIG)
    config["runtime"]["auto_reload"] = "lazy"
    k.set_user_config(SetUserConfigRequest(config=config))
    await k.run(
        [
            er_1 := exec_req.get(f"from {py_modname} import foo"),
            er_2 := exec_req.get("x = foo()"),
            er_3 := exec_req.get("pass"),
        ]
    )
    assert k.globals["x"] == 1
    update_file(
        py_file,
        """
        def foo():
            return 2
        """,
    )

    # wait for the watcher to pick up the change
    await asyncio.sleep(2.5)
    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    await k.run_stale_cells()
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    assert k.globals["x"] == 2


async def test_reload_nested_module_function(
    tmp_path: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
):
    k = execution_kernel
    sys.path.append(str(tmp_path))
    b = tmp_path / (b_name := random_modname())
    b.mkdir()
    (b / "__init__.py").write_text("")

    c = b / (c_name := random_modname())
    c.mkdir()
    (c / "__init__.py").write_text("")

    nested_module = c / "mod.py"
    nested_module.write_text("func = lambda: 1")
    py_file = tmp_path / pathlib.Path(py_modname + ".py")
    py_file.write_text(
        textwrap.dedent(
            f"""
            from {b_name}.{c_name}.mod import func

            def foo():
                return func()
            """
        )
    )

    config = copy.deepcopy(DEFAULT_CONFIG)
    config["runtime"]["auto_reload"] = "lazy"
    k.set_user_config(SetUserConfigRequest(config=config))
    await k.run(
        [
            er_1 := exec_req.get(f"from {py_modname} import foo"),
            er_2 := exec_req.get("x = foo()"),
            er_3 := exec_req.get("pass"),
        ]
    )
    assert k.globals["x"] == 1
    update_file(nested_module, "func = lambda : 2")

    # wait for the watcher to pick up the change
    await asyncio.sleep(2.5)
    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    await k.run_stale_cells()
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    assert k.globals["x"] == 2


async def test_reload_nested_module_import_module(
    tmp_path: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
):
    k = execution_kernel
    sys.path.append(str(tmp_path))
    b = tmp_path / (b_name := random_modname())
    b.mkdir()
    (b / "__init__.py").write_text("")

    c = b / (c_name := random_modname())
    c.mkdir()
    (c / "__init__.py").write_text("")

    nested_module = c / "mod.py"
    nested_module.write_text("func = lambda: 1")
    py_file = tmp_path / pathlib.Path(py_modname + ".py")
    py_file.write_text(
        textwrap.dedent(
            f"""
            from {b_name}.{c_name} import mod

            def foo():
                return mod.func()
            """
        )
    )

    config = copy.deepcopy(DEFAULT_CONFIG)
    config["runtime"]["auto_reload"] = "lazy"
    k.set_user_config(SetUserConfigRequest(config=config))
    await k.run(
        [
            er_1 := exec_req.get(f"from {py_modname} import foo"),
            er_2 := exec_req.get("x = foo()"),
            er_3 := exec_req.get("pass"),
        ]
    )
    assert k.globals["x"] == 1
    update_file(nested_module, "func = lambda : 2")

    # wait for the watcher to pick up the change
    await asyncio.sleep(2.5)
    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    await k.run_stale_cells()
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    assert k.globals["x"] == 2


# TODO(akshayka): deflake this test
@pytest.mark.xfail(
    condition=sys.version_info[0] == 3 and sys.version_info[1] == 8,
    reason="Timing dependent test is flaky, needs investigation",
    strict=False,
)
async def test_reload_nested_module_import_module_autorun(
    tmp_path: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
):
    k = execution_kernel
    sys.path.append(str(tmp_path))
    b = tmp_path / (b_name := random_modname())
    b.mkdir()
    (b / "__init__.py").write_text("")

    c = b / (c_name := random_modname())
    c.mkdir()
    (c / "__init__.py").write_text("")

    nested_module = c / "mod.py"
    nested_module.write_text("func = lambda: 1")
    py_file = tmp_path / pathlib.Path(py_modname + ".py")
    py_file.write_text(
        textwrap.dedent(
            f"""
            from {b_name}.{c_name} import mod

            def foo():
                return mod.func()
            """
        )
    )

    queue = Queue()
    k.enqueue_control_request = lambda req: queue.put(req)
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["runtime"]["auto_reload"] = "autorun"
    k.set_user_config(SetUserConfigRequest(config=config))
    await k.run(
        [
            er_1 := exec_req.get(f"from {py_modname} import foo"),
            er_2 := exec_req.get("x = foo()"),
            er_3 := exec_req.get("pass"),
        ]
    )
    assert k.globals["x"] == 1
    update_file(nested_module, "func = lambda: 2")

    # wait for the watcher to pick up the change
    queue.get(timeout=3)
    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    await k.run_stale_cells()
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    assert k.globals["x"] == 2


async def test_reload_package(
    tmp_path: pathlib.Path,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
):
    k = execution_kernel
    sys.path.append(str(tmp_path))
    b = tmp_path / (b_name := random_modname())
    b.mkdir()
    c = b / (c_name := random_modname())
    c.mkdir()
    (b / "__init__.py").write_text(f"from {b_name}.{c_name}.mod import func")
    (c / "__init__.py").write_text("")

    nested_module = c / "mod.py"
    nested_module.write_text("func = lambda: 1")

    config = copy.deepcopy(DEFAULT_CONFIG)
    config["runtime"]["auto_reload"] = "lazy"
    k.set_user_config(SetUserConfigRequest(config=config))
    await k.run(
        [
            er_1 := exec_req.get(f"import {b_name}"),
            er_2 := exec_req.get(f"x = {b_name}.func()"),
            er_3 := exec_req.get("pass"),
        ]
    )
    assert not k.errors
    assert k.globals[b_name]
    assert k.globals["x"] == 1
    update_file(nested_module, "func = lambda : 2")

    # wait for the watcher to pick up the change
    await asyncio.sleep(2.5)
    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    await k.run_stale_cells()
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    assert k.globals["x"] == 2


@pytest.mark.skipif(
    not DependencyManager.has_numpy(), reason="NumPy not installed"
)
async def test_reload_third_party(
    tmp_path: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
):
    k = execution_kernel
    # make sure that importing a third-party package like numpy doesn't
    # break the module finder
    sys.path.append(str(tmp_path))
    py_file = tmp_path / pathlib.Path(py_modname + ".py")
    py_file.write_text(
        textwrap.dedent(
            """
            import numpy as np

            def foo():
                return 1
            """
        )
    )

    config = copy.deepcopy(DEFAULT_CONFIG)
    config["runtime"]["auto_reload"] = "lazy"
    k.set_user_config(SetUserConfigRequest(config=config))
    await k.run(
        [
            er_1 := exec_req.get(f"from {py_modname} import foo"),
            er_2 := exec_req.get("x = foo()"),
            er_3 := exec_req.get("pass"),
        ]
    )
    assert k.globals["x"] == 1
    update_file(
        py_file,
        """
        def foo():
            return 2
        """,
    )

    # wait for the watcher to pick up the change
    await asyncio.sleep(2.5)
    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    await k.run_stale_cells()
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    assert k.globals["x"] == 2


async def test_reload_with_modified_cell(
    tmp_path: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
):
    k = execution_kernel
    sys.path.append(str(tmp_path))
    py_file = tmp_path / pathlib.Path(py_modname + ".py")
    py_file.write_text(
        textwrap.dedent(
            """
            def foo():
                return 1
            """
        )
    )

    config = copy.deepcopy(DEFAULT_CONFIG)
    config["runtime"]["auto_reload"] = "lazy"
    k.set_user_config(SetUserConfigRequest(config=config))
    await k.run(
        [
            er_1 := exec_req.get(f"from {py_modname} import foo"),
            er_2 := exec_req.get("x = foo()"),
            er_3 := exec_req.get("pass"),
        ]
    )
    assert k.globals["x"] == 1
    update_file(
        py_file,
        """
        def foo():
            return 2
        """,
    )

    # wait for the watcher to pick up the change
    await asyncio.sleep(2.5)
    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale

    # modify the first cell and make sure it is still marked as stale;
    k._maybe_register_cell(er_1.cell_id, f"from {py_modname} import foo; 1")
    assert er_1.cell_id in k.graph.get_stale()
