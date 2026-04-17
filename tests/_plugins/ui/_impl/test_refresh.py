from __future__ import annotations

from marimo._plugins import ui
from marimo._runtime.commands import UpdateUIElementCommand
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


def test_refresh_initial_value_is_empty_string():
    refresh = ui.refresh(options=["1s", "5s"], default_interval="1s")
    assert refresh.value == ""


async def test_refresh_value_updates_to_frontend_string(
    any_kernel: Kernel, exec_req: ExecReqProvider
):
    k = any_kernel
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("r = mo.ui.refresh(options=['1s', '5s'])"),
        ]
    )

    refresh = k.globals["r"]
    assert refresh.value == ""

    await k.set_ui_element_value(
        UpdateUIElementCommand([refresh._id], ["1s (0)"])
    )
    assert refresh.value == "1s (0)"


def test_refresh_on_change_receives_string():
    seen: list[str] = []
    refresh = ui.refresh(
        options=["1s"], default_interval="1s", on_change=seen.append
    )
    refresh._update("1s (0)")
    refresh._update("1s (1)")
    assert seen == ["1s (0)", "1s (1)"]
