import pathlib
import sys
import textwrap
import time

from marimo._config.config import DEFAULT_CONFIG
from marimo._runtime.runtime import Kernel
from marimo._runtime.requests import SetUserConfigRequest
from tests.conftest import ExecReqProvider
from reload_test_utils import update_file


async def test_reload_function_kernel(
    tmp_path: pathlib.Path,
    py_modname: str,
    k: Kernel,
    exec_req: ExecReqProvider,
):
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

    config = DEFAULT_CONFIG.copy()
    config["runtime"]["auto_reload"] = "detect"
    k.set_user_config(SetUserConfigRequest(config=config))
    await k.run(
        [
            er_1 := exec_req.get(f"from {py_modname} import foo"),
            er_2 := exec_req.get(f"x = foo()"),
            er_3 := exec_req.get(f"pass"),
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
    time.sleep(1.5)
    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    await k.run_stale_cells()
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    assert k.globals["x"] == 2
