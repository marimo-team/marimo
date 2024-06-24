from marimo._plugins import ui
from marimo._runtime.requests import SetUIElementValueRequest
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


def test_run_button_initial_value():
    run_button = ui.run_button()
    assert not run_button.value


async def test_run_button_set_to_true_on_click(
    any_kernel: Kernel, exec_req: ExecReqProvider
):
    k = any_kernel
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("b = mo.ui.run_button()"),
            er := exec_req.get(
                """
                if b.value:
                    x = 1
                else:
                    x = 0
                """
            ),
        ]
    )

    run_button = k.globals["b"]
    assert not run_button.value

    await k.set_ui_element_value(
        SetUIElementValueRequest([run_button._id], [1])
    )

    if not k.lazy():
        assert k.globals["x"] == 1
        assert not run_button.value
    else:
        # value is updated ...
        assert run_button.value
        # ... but we haven't run its descendants yet
        assert k.globals["x"] == 0

        await k.run([er])

        assert k.globals["x"] == 1
        # in lazy kernels, run button's value is not set to False, since
        # we don't know when its descendants have run
        assert run_button.value
