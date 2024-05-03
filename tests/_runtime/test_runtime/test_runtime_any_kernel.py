# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import TYPE_CHECKING


from marimo._config.config import DEFAULT_CONFIG
from marimo._messaging.types import NoopStream
from marimo._runtime.requests import (
    AppMetadata,
    SetCellConfigRequest,
    SetUIElementValueRequest,
)
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    import pathlib
    from types import ModuleType


class TestWithAnyKernel:
    """Tests that run on any type of kernel."""

    async def test_set_ui_element_value_not_found_doesnt_fail(
        self,
        any_kernel: Kernel,
    ) -> None:
        # smoke test -- this shouldn't raise an exception
        k = any_kernel
        await k.set_ui_element_value(
            SetUIElementValueRequest([("does not exist", None)])
        )

    async def test_interrupt(
        self, any_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = any_kernel
        er = exec_req.get(
            """
            from marimo._runtime.control_flow import MarimoInterrupt

            tries = 0
            while tries < 5:
                try:
                    raise MarimoInterrupt
                except Exception:
                    ...
                tries += 1
            """
        )
        await k.run([er])
        # make sure the interrupt wasn't caught by the try/except
        assert k.globals["tries"] == 0

    async def test_running_in_notebook(
        self, any_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = any_kernel
        await k.run(
            [
                exec_req.get(
                    "import marimo as mo; in_nb = mo.running_in_notebook()"
                )
            ]
        )
        assert k.globals["in_nb"]

    async def test_file_path(
        self, any_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = any_kernel
        await k.run(
            [
                exec_req.get("import marimo as mo"),
                exec_req.get("x = __file__"),
            ]
        )

        assert "pytest" in k.globals["x"]

    async def test_pickle(
        self, any_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = any_kernel
        await k.run(
            [
                exec_req.get("import pickle"),
                exec_req.get(
                    """
                    def foo():
                        ...

                    pickle_output = None
                    pickle_output = pickle.dumps(foo)
                    """
                ),
            ]
        )
        assert k.globals["pickle_output"] is not None

    def test_sys_path_updated(self, tmp_path: pathlib.Path) -> None:
        main: ModuleType | None = None
        try:
            filename = str(tmp_path / "notebook.py")
            if "__main__" in sys.modules:
                # kernel patches __main__; need to reset it after test
                main = sys.modules["__main__"]
            Kernel(
                stream=NoopStream(),
                stdout=None,
                stderr=None,
                stdin=None,
                cell_configs={},
                user_config=DEFAULT_CONFIG,
                app_metadata=AppMetadata(
                    query_params={}, filename=filename, cli_args={}
                ),
                enqueue_control_request=lambda _: None,
            )
            assert str(tmp_path) in sys.path
            assert str(tmp_path) == sys.path[0]
        finally:
            if str(tmp_path) in sys.path:
                sys.path.remove(str(tmp_path))
            if main is not None:
                sys.modules["__main__"] = main

    async def test_set_config_before_registering_cell(
        self, any_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = any_kernel
        er_1 = exec_req.get("x = 0")
        await k.set_cell_config(
            SetCellConfigRequest(configs={er_1.cell_id: {"disabled": True}})
        )
        await k.run([er_1])
        assert k.graph.cells[er_1.cell_id].config.disabled
        assert "x" not in k.globals
