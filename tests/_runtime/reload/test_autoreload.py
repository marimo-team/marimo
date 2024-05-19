from __future__ import annotations

import importlib
import pathlib
import sys
import textwrap

from reload_test_utils import update_file

from marimo._runtime.reload.autoreload import (
    ModuleDependencyFinder,
    ModuleReloader,
)


def test_reload_function(tmp_path: pathlib.Path, py_modname: str):
    sys.path.append(str(tmp_path))
    reloader = ModuleReloader()
    py_file = tmp_path / pathlib.Path(py_modname + ".py")
    py_file.write_text(
        textwrap.dedent(
            """
            def foo():
                return 1
            """
        )
    )
    mod = importlib.import_module(py_modname)
    reloader.check(sys.modules, reload=False)
    assert mod.foo() == 1
    update_file(
        py_file,
        """
        def foo():
            return 2
        """,
    )
    reloader.check(sys.modules, reload=True)
    assert mod.foo() == 2


def test_reload_module_with_error(tmp_path: pathlib.Path, py_modname: str):
    sys.path.append(str(tmp_path))
    reloader = ModuleReloader()
    py_file = tmp_path / pathlib.Path(py_modname + ".py")
    py_file.write_text(
        textwrap.dedent(
            """
            def foo():
                return 1
            """
        )
    )
    mod = importlib.import_module(py_modname)
    reloader.check(sys.modules, reload=False)
    assert mod.foo() == 1
    update_file(
        py_file,
        """
        import this_module_does_not_exist
        def foo():
            return 2
        """,
    )
    reloader.check(sys.modules, reload=True)

    assert str(py_file) in reloader.failed
    # module is still in sys.modules ...
    assert py_modname in sys.modules
    # ... but it's basically empty
    assert not hasattr(mod, "foo")


def test_reload_module_with_syntax_error(
    tmp_path: pathlib.Path, py_modname: str
):
    sys.path.append(str(tmp_path))
    reloader = ModuleReloader()
    py_file = tmp_path / pathlib.Path(py_modname + ".py")
    py_file.write_text(
        textwrap.dedent(
            """
            def foo():
                return 1
            """
        )
    )
    mod = importlib.import_module(py_modname)
    reloader.check(sys.modules, reload=False)
    assert mod.foo() == 1
    update_file(
        py_file,
        """
        t h _ i s is in va lid python
        """,
    )
    reloader.check(sys.modules, reload=True)

    assert str(py_file) in reloader.failed
    # module is still in sys.modules ...
    assert py_modname in sys.modules
    # ... but it's basically empty
    assert not hasattr(mod, "foo")


class TestModuleDependencyFinder:
    def test_dependencies_isolated(self):
        from tests._runtime.reload.reload_data import a, b, c, d

        finder = ModuleDependencyFinder()
        a_deps = set(list(finder.find_dependencies(a, excludes=[]).keys()))
        b_deps = set(list(finder.find_dependencies(b, excludes=[]).keys()))
        c_deps = set(list(finder.find_dependencies(c, excludes=[]).keys()))
        d_deps = set(list(finder.find_dependencies(d, excludes=[]).keys()))

        assert a_deps == set(["__main__", "reload_data", "reload_data.c"])
        assert b_deps == set(["__main__", "reload_data", "reload_data.d"])
        assert c_deps == set(["__main__"])
        assert d_deps == set(["__main__"])

    def test_dependencies_cached(self):
        from tests._runtime.reload.reload_data import a

        finder = ModuleDependencyFinder()
        assert not finder.cached(a)

        finder.find_dependencies(a, excludes=[])
        assert finder.cached(a)

        finder.evict_from_cache(a)
        assert not finder.cached(a)
