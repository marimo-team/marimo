from __future__ import annotations

import importlib
import pathlib
import sys
import textwrap

from marimo._runtime.reload.autoreload import ModuleReloader
from reload_test_utils import update_file


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
