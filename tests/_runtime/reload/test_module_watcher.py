from __future__ import annotations

import asyncio
import copy
import pathlib
import sys
import textwrap
import types
from queue import Queue

import pytest
from reload_test_utils import random_modname, update_file

from marimo._config.config import DEFAULT_CONFIG
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.reload.autoreload import ModuleReloader
from marimo._runtime.reload.module_watcher import (
    _check_modules,
    _depends_on,
    _get_excluded_modules,
)
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
    retries = 0
    while retries < 10:
        await asyncio.sleep(INTERVAL)
        retries += 1
        if k.graph.cells[er_1.cell_id].stale:
            break

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
        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # Module without __file__ attribute
        mod = types.ModuleType("test_module")
        assert not _is_third_party_module(mod)

    def test_module_with_none_file(self):
        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # Module with __file__ = None
        mod = types.ModuleType("test_module")
        mod.__file__ = None
        assert not _is_third_party_module(mod)

    def test_site_packages_module(self):
        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # Module in site-packages
        mod = types.ModuleType("test_module")
        mod.__file__ = "/usr/lib/python3.10/site-packages/numpy/__init__.py"
        assert _is_third_party_module(mod)

    def test_local_module(self):
        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # Local module not in site-packages
        mod = types.ModuleType("test_module")
        mod.__file__ = "/home/user/project/mymodule.py"
        assert not _is_third_party_module(mod)

    def test_site_packages_in_path_but_not_directory(self):
        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # Edge case: "site-packages" appears in filename but not as directory
        mod = types.ModuleType("test_module")
        mod.__file__ = "/home/user/site-packages.py"
        assert not _is_third_party_module(mod)

    def test_actual_third_party_module(self):
        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # pytest should be in site-packages
        assert _is_third_party_module(pytest)

    def test_builtin_module(self):
        from marimo._runtime.reload.module_watcher import (
            _is_third_party_module,
        )

        # Builtin modules typically don't have __file__ or have None
        assert not _is_third_party_module(sys)


class TestDependsOn:
    """Unit tests for the _depends_on function"""

    def test_depends_on_direct_match(self):
        """Test _depends_on returns True when src is in target_modules"""
        src_module = types.ModuleType("src")
        target_module = types.ModuleType("target")
        target_modules = {src_module, target_module}
        target_filenames = set()
        reloader = ModuleReloader()

        result = _depends_on(
            src_module, target_modules, target_filenames, set(), reloader
        )
        assert result is True

    def test_depends_on_by_filename(self, tmp_path: pathlib.Path):
        """Test _depends_on detects dependency by filename"""
        # Create a module with a file
        py_file = tmp_path / "test_mod.py"
        py_file.write_text("x = 1")

        src_module = types.ModuleType("src")
        src_module.__file__ = str(py_file)

        target_modules = set()
        target_filenames = {str(py_file)}
        reloader = ModuleReloader()

        result = _depends_on(
            src_module, target_modules, target_filenames, set(), reloader
        )
        assert result is True

    def test_depends_on_package_submodule(self):
        """Test _depends_on detects package dependencies"""
        # Create a package module (ends with __init__.py)
        src_module = types.ModuleType("mypackage")
        src_module.__file__ = "/path/to/mypackage/__init__.py"
        src_module.__name__ = "mypackage"

        target_module = types.ModuleType("mypackage.submodule")
        target_module.__name__ = "mypackage.submodule"
        target_module.__file__ = "/path/to/mypackage/submodule.py"

        target_modules = {target_module}
        target_filenames = {"/path/to/mypackage/submodule.py"}
        reloader = ModuleReloader()

        result = _depends_on(
            src_module, target_modules, target_filenames, set(), reloader
        )
        assert result is True

    def test_depends_on_no_dependency(self):
        """Test _depends_on returns False when no dependency"""
        src_module = types.ModuleType("src")
        src_module.__file__ = "/path/to/src.py"

        target_module = types.ModuleType("target")
        target_module.__file__ = "/path/to/target.py"

        target_modules = {target_module}
        target_filenames = {"/path/to/target.py"}
        reloader = ModuleReloader()

        result = _depends_on(
            src_module, target_modules, target_filenames, set(), reloader
        )
        assert result is False

    def test_depends_on_module_without_file(self):
        """Test _depends_on with module without __file__"""
        src_module = types.ModuleType("src")
        # No __file__ attribute

        target_modules = set()
        target_filenames = set()
        reloader = ModuleReloader()

        result = _depends_on(
            src_module, target_modules, target_filenames, set(), reloader
        )
        assert result is False


class TestGetExcludedModules:
    """Unit tests for the _get_excluded_modules function"""

    def test_get_excluded_modules_filters_site_packages(self):
        """Test _get_excluded_modules returns site-packages modules"""
        mod1 = types.ModuleType("local_mod")
        mod1.__file__ = "/home/user/project/local_mod.py"

        mod2 = types.ModuleType("third_party")
        mod2.__file__ = "/usr/lib/python3.10/site-packages/third_party.py"

        modules = {"local_mod": mod1, "third_party": mod2}

        result = _get_excluded_modules(modules)
        assert "third_party" in result
        assert "local_mod" not in result

    def test_get_excluded_modules_caching(self):
        """Test _get_excluded_modules uses cache"""
        mod1 = types.ModuleType("mod1")
        mod1.__file__ = "/usr/lib/python3.10/site-packages/mod1.py"

        modules = {"mod1": mod1}

        # First call should compute
        result1 = _get_excluded_modules(modules)
        assert "mod1" in result1

        # Second call with same modules should use cache
        result2 = _get_excluded_modules(modules)
        assert result2 is result1  # Same object reference

    def test_get_excluded_modules_cache_invalidation(self):
        """Test _get_excluded_modules cache updates with different modules"""
        mod1 = types.ModuleType("mod1")
        mod1.__file__ = "/usr/lib/python3.10/site-packages/mod1.py"

        modules1 = {"mod1": mod1}
        result1 = _get_excluded_modules(modules1)

        # Different set of modules should recompute
        mod2 = types.ModuleType("mod2")
        mod2.__file__ = "/usr/lib/python3.10/site-packages/mod2.py"

        modules2 = {"mod2": mod2}
        result2 = _get_excluded_modules(modules2)

        assert result1 != result2
        assert "mod1" in result1
        assert "mod2" in result2

    def test_get_excluded_modules_empty(self):
        """Test _get_excluded_modules with no third-party modules"""
        mod1 = types.ModuleType("local_mod")
        mod1.__file__ = "/home/user/project/local_mod.py"

        modules = {"local_mod": mod1}

        result = _get_excluded_modules(modules)
        assert result == set()


class TestCheckModules:
    """Unit tests for the _check_modules function"""

    def test_check_modules_detects_stale(self, tmp_path: pathlib.Path):
        """Test _check_modules detects stale modules"""
        import importlib

        sys.path.append(str(tmp_path))
        py_file = tmp_path / "test_check_mod.py"
        py_file.write_text("x = 1")

        mod = importlib.import_module("test_check_mod")
        reloader = ModuleReloader()
        reloader.check(sys.modules, reload=False)

        # Modify the file
        update_file(py_file, "x = 2")

        # _check_modules should detect it's stale
        modules = {"test_check_mod": mod}
        stale = _check_modules(modules, reloader, sys.modules)

        assert "test_check_mod" in stale

    def test_check_modules_no_stale(self):
        """Test _check_modules with no stale modules"""
        reloader = ModuleReloader()
        modules = {"os": sys.modules["os"]}

        stale = _check_modules(modules, reloader, sys.modules)
        assert len(stale) == 0

    def test_check_modules_empty_input(self):
        """Test _check_modules with empty modules dict"""
        reloader = ModuleReloader()
        modules = {}

        stale = _check_modules(modules, reloader, sys.modules)
        assert len(stale) == 0


class TestModuleWatcherStop:
    """Tests for ModuleWatcher.stop method"""

    async def test_module_watcher_stop(
        self, execution_kernel: Kernel, exec_req: ExecReqProvider
    ):
        """Test that ModuleWatcher.stop sets the exit event"""
        del exec_req
        k = execution_kernel
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["runtime"]["auto_reload"] = "lazy"
        k.set_user_config(SetUserConfigRequest(config=config))

        # Give watcher time to start
        await asyncio.sleep(INTERVAL)

        # Stop the watcher
        assert k.module_watcher is not None
        assert not k.module_watcher.should_exit.is_set()

        k.module_watcher.stop()

        # should_exit should be set
        assert k.module_watcher.should_exit.is_set()

    async def test_module_watcher_processes_flag(
        self, execution_kernel: Kernel, exec_req: ExecReqProvider
    ):
        """Test ModuleWatcher run_is_processed flag behavior"""
        del exec_req
        k = execution_kernel
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["runtime"]["auto_reload"] = "lazy"
        k.set_user_config(SetUserConfigRequest(config=config))

        # Give watcher time to start
        await asyncio.sleep(INTERVAL)

        assert k.module_watcher is not None
        # Initially should be set (no run in flight)
        assert k.module_watcher.run_is_processed.is_set()


class TestModuleWatcherEdgeCases:
    """Tests for edge cases in module watching"""

    async def test_module_watcher_handles_deleted_cell(
        self,
        tmp_path: pathlib.Path,
        py_modname: str,
        execution_kernel: Kernel,
        exec_req: ExecReqProvider,
    ):
        """Test watcher handles cells being deleted from graph"""
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
            ]
        )
        assert k.globals["x"] == 1

        # Delete a cell from the graph
        await k.delete_cell(er_2)

        # Modify the file
        update_file(
            py_file,
            """
            def foo():
                return 2
            """,
        )

        # Wait for watcher to pick up change
        await asyncio.sleep(INTERVAL * 3)

        # Only er_1 should be stale (er_2 was deleted)
        assert k.graph.cells[er_1.cell_id].stale
        assert er_2.cell_id not in k.graph.cells

    async def test_module_watcher_cache_invalidation(
        self,
        tmp_path: pathlib.Path,
        py_modname: str,
        execution_kernel: Kernel,
        exec_req: ExecReqProvider,
    ):
        """Test that cell modules cache is properly invalidated"""
        k = execution_kernel
        sys.path.append(str(tmp_path))
        py_file = tmp_path / pathlib.Path(py_modname + ".py")
        py_file.write_text("def foo(): return 1")

        config = copy.deepcopy(DEFAULT_CONFIG)
        config["runtime"]["auto_reload"] = "lazy"
        k.set_user_config(SetUserConfigRequest(config=config))

        # Run a cell with import
        await k.run([er_1 := exec_req.get(f"from {py_modname} import foo")])

        # Modify the module
        update_file(py_file, "def foo(): return 2")

        # Wait for watcher
        await asyncio.sleep(INTERVAL * 3)
        assert k.graph.cells[er_1.cell_id].stale

        # Run stale cells
        await k.run_stale_cells()

        # Now modify the cell's imports (simulate changing the import)
        # This should invalidate the cache
        await k.run(
            [exec_req.get(f"from {py_modname} import foo; import sys")]
        )

        # The cache should handle the modified imports correctly
        assert not k.graph.cells[er_1.cell_id].stale
