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

INTERVAL = 0.2


@pytest.fixture(autouse=True)
def _setup_test_sleep():
    """Automatically set up faster sleep interval for all tests in this module"""
    import marimo._runtime.reload.module_watcher as mw

    old_interval = mw._TEST_SLEEP_INTERVAL
    mw._TEST_SLEEP_INTERVAL = INTERVAL
    yield
    mw._TEST_SLEEP_INTERVAL = old_interval


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
    await asyncio.sleep(INTERVAL * 3)
    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    await k.run_stale_cells()
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    assert k.globals["x"] == 2


@pytest.mark.flaky(reruns=5)
async def test_disable_and_reenable_reload(
    tmp_path: pathlib.Path,
    py_modname: str,
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
):
    # tests a bug in which after disabling the reloader, it couldn't be
    # reenabled
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
    # enable reloading ...
    config["runtime"]["auto_reload"] = "lazy"
    k.set_user_config(SetUserConfigRequest(config=config))

    # disable it ...
    config["runtime"]["auto_reload"] = "off"
    k.set_user_config(SetUserConfigRequest(config=config))

    # TODO: Invesitigate flaky on minimal CI
    await asyncio.sleep(INTERVAL / 2)

    # ... and reenable it
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
    await asyncio.sleep(INTERVAL * 3)
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
    await asyncio.sleep(INTERVAL * 3)
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
    await asyncio.sleep(INTERVAL * 3)
    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    await k.run_stale_cells()
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    assert k.globals["x"] == 2


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
    await asyncio.sleep(INTERVAL * 3)
    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    await k.run_stale_cells()
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    assert k.globals["x"] == 2


@pytest.mark.skipif(
    not DependencyManager.numpy.has(), reason="NumPy not installed"
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
    await asyncio.sleep(INTERVAL * 3)
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
    await asyncio.sleep(INTERVAL * 3)
    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale

    # modify the first cell and make sure it is still marked as stale;
    k._maybe_register_cell(
        er_1.cell_id, f"from {py_modname} import foo; 1", stale=False
    )
    assert er_1.cell_id in k.graph.get_stale()


@pytest.mark.xfail(
    True,
    reason=(
        "watcher sometimes takes a long time to pick up file change to "
        "an import block on CI"
    ),
    strict=False,
)
async def test_reload_function_in_import_block(
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
            # We will modify py_modname but not "random" ...
            er_1 := exec_req.get(
                f"import random; from {py_modname} import foo"
            ),
            er_2 := exec_req.get("x = foo()"),
            er_3 := exec_req.get("pass"),
            er_4 := exec_req.get("y = random.randint(0, 10000000)"),
            er_5 := exec_req.get("random, foo"),
        ]
    )
    assert k.globals["x"] == 1
    y = k.globals["y"]

    update_file(
        py_file,
        """
        def foo():
            return 2
        """,
    )

    # wait for the watcher to pick up the change
    retries = 0
    while retries < 10:
        await asyncio.sleep(INTERVAL)
        retries += 1
        if k.graph.cells[er_1.cell_id].stale:
            break

    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    # "random" wasn't modified, so it should be pruned from descendants
    assert not k.graph.cells[er_4.cell_id].stale
    # er_5 depends on random and foo, and foo is stale
    assert k.graph.cells[er_5.cell_id].stale

    await k.run_stale_cells()
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    assert k.globals["x"] == 2
    assert k.globals["y"] == y


class TestIsSubmodule:
    """Unit tests for the is_submodule utility function"""

    def test_parent_child_relationship(self):
        from marimo._runtime.reload.module_watcher import is_submodule

        # Parent is a submodule of child
        assert is_submodule("marimo", "marimo.plugins")
        assert is_submodule("marimo.plugins", "marimo.plugins.ui")
        assert is_submodule("a.b", "a.b.c.d")

    def test_exact_match(self):
        from marimo._runtime.reload.module_watcher import is_submodule

        # Module is a submodule of itself
        assert is_submodule("marimo", "marimo")
        assert is_submodule("marimo.plugins", "marimo.plugins")
        assert is_submodule("a.b.c", "a.b.c")

    def test_not_submodule(self):
        from marimo._runtime.reload.module_watcher import is_submodule

        # Different modules
        assert not is_submodule("marimo", "numpy")
        assert not is_submodule("marimo.plugins", "marimo.runtime")
        assert not is_submodule("a.b.c", "a.b.d")

    def test_longer_src_than_target(self):
        from marimo._runtime.reload.module_watcher import is_submodule

        # Src is longer than target - can't be parent
        assert not is_submodule("marimo.plugins.ui", "marimo.plugins")
        assert not is_submodule("marimo.plugins", "marimo")
        assert not is_submodule("a.b.c", "a.b")

    def test_similar_names_not_submodule(self):
        from marimo._runtime.reload.module_watcher import is_submodule

        # Make sure "foo" doesn't match "foobar"
        assert not is_submodule("foo", "foobar")
        assert not is_submodule("marimo", "marimo_extra")
        assert not is_submodule("a.b", "a.bc")

    def test_empty_strings(self):
        from marimo._runtime.reload.module_watcher import is_submodule

        # Edge cases with empty strings
        assert is_submodule("", "")
        # Empty string is not a valid parent module
        assert not is_submodule("", "marimo")
        assert not is_submodule("marimo", "")


class TestIsThirdPartyModule:
    """Unit tests for the _is_third_party_module utility function"""

    def test_module_without_file(self):
        import types

        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # Module without __file__ attribute
        mod = types.ModuleType("test_module")
        assert not _is_third_party_module(mod)

    def test_module_with_none_file(self):
        import types

        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # Module with __file__ = None
        mod = types.ModuleType("test_module")
        mod.__file__ = None
        assert not _is_third_party_module(mod)

    def test_site_packages_module(self):
        import types

        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # Module in site-packages
        mod = types.ModuleType("test_module")
        mod.__file__ = "/usr/lib/python3.10/site-packages/numpy/__init__.py"
        assert _is_third_party_module(mod)

    def test_local_module(self):
        import types

        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # Local module not in site-packages
        mod = types.ModuleType("test_module")
        mod.__file__ = "/home/user/project/mymodule.py"
        assert not _is_third_party_module(mod)

    def test_site_packages_in_path_but_not_directory(self):
        import types

        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # Edge case: "site-packages" appears in filename but not as directory
        mod = types.ModuleType("test_module")
        mod.__file__ = "/home/user/site-packages.py"
        assert _is_third_party_module(mod)

    def test_actual_third_party_module(self):
        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # Test with an actual third-party module if available
        try:
            import pytest

            # pytest should be in site-packages
            assert _is_third_party_module(pytest)
        except ImportError:
            pytest.skip("pytest not available")

    def test_builtin_module(self):
        import sys

        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # Builtin modules typically don't have __file__ or have None
        assert not _is_third_party_module(sys)
