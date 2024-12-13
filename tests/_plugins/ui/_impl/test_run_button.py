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


async def test_run_buttons_in_array(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(
                "arr = mo.ui.array([mo.ui.run_button(), mo.ui.run_button()])"
            ),
            exec_req.get("count = [0]"),
            exec_req.get(
                """
                for b in arr:
                    if b.value:
                        count[0] += 1
                """
            ),
        ]
    )

    arr = k.globals["arr"]
    count = k.globals["count"]
    assert not arr.value[0]
    assert not arr.value[1]
    # No buttons yet pushed
    assert count[0] == 0

    # Just one button pushed
    await k.set_ui_element_value(SetUIElementValueRequest([arr[0]._id], [1]))
    assert count[0] == 1
    assert not arr.value[0]
    assert not arr.value[1]
    # Push another button, first button's value should be false, so just an
    # increment by 1
    await k.set_ui_element_value(SetUIElementValueRequest([arr[1]._id], [1]))
    assert count[0] == 2
    assert not arr.value[0]
    assert not arr.value[1]


async def test_run_buttons_in_dict(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(
                """
                hoc = mo.ui.dictionary(
                    {'0': mo.ui.run_button(), '1': mo.ui.run_button()}
                )
                """
            ),
            exec_req.get("count = [0]"),
            exec_req.get(
                """
                for b in hoc.values():
                    if b.value:
                        count[0] += 1
                """
            ),
        ]
    )

    hoc = k.globals["hoc"]
    count = k.globals["count"]
    assert not hoc.value["0"]
    assert not hoc.value["1"]
    # No buttons yet pushed
    assert count[0] == 0

    # Just one button pushed
    await k.set_ui_element_value(SetUIElementValueRequest([hoc["0"]._id], [1]))
    assert count[0] == 1
    assert not hoc.value["0"]
    assert not hoc.value["1"]
    # Push another button, first button's value should be false, so just an
    # increment by 1
    await k.set_ui_element_value(SetUIElementValueRequest([hoc["1"]._id], [1]))
    assert count[0] == 2
    assert not hoc.value["0"]
    assert not hoc.value["1"]
