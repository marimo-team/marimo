from __future__ import annotations

import importlib
import pathlib
import random
import sys
import textwrap
import time

from marimo._config.config import DEFAULT_CONFIG
from marimo._runtime.autoreload import ModuleReloader
from marimo._runtime.requests import SetUserConfigRequest
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


def random_py_modname() -> str:
    filename_chars = "abcdefghijklmopqrstuvwxyz"
    return "".join(random.sample(filename_chars, 20))


def update_file(path: pathlib.Path, code: str) -> None:
    """
    Comment from
    https://github.com/ipython/ipython/blob/fe52b206ecd0e566fff935fea36d26e0903ec34b/IPython/extensions/tests/test_autoreload.py#L128

    Python's .pyc files record the timestamp of their compilation
    with a time resolution of one second.

    Therefore, we need to force a timestamp difference between .py
    and .pyc, without having the .py file be timestamped in the
    future, and without changing the timestamp of the .pyc file
    (because that is stored in the file).  The only reliable way
    to achieve this seems to be to sleep.
    """
    time.sleep(1.05)
    path.write_text(textwrap.dedent(code))


def test_reload_function(tmp_path: pathlib.Path):
    sys.path.append(str(tmp_path))
    reloader = ModuleReloader()
    py_modname = random_py_modname()
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


async def test_reload_function_kernel(
    tmp_path: pathlib.Path, k: Kernel, exec_req: ExecReqProvider
):
    sys.path.append(str(tmp_path))
    py_modname = random_py_modname()
    py_file = tmp_path / pathlib.Path(py_modname + ".py")
    py_file.write_text(
        textwrap.dedent(
            """
            def foo():
                return 1
            """
        )
    )

    config = DEFAULT_CONFIG.copy()
    config["runtime"]["auto_reload"] = True
    k.set_user_config(SetUserConfigRequest(config=config))
    await k.run([exec_req.get(f"import {py_modname}; x={py_modname}.foo()")])
    assert k.globals["x"] == 1
    update_file(
        py_file,
        """
        def foo():
            return 2
        """,
    )

    await k.run([exec_req.get(f"y={py_modname}.foo()")])
    assert k.globals["y"] == 2
