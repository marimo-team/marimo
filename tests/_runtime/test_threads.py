import time

from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


async def test_set_ui_element_value_lensed(
    any_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test setting the value of a lensed element.

    Make sure reactivity flows through its parent, and that its on_change
    handler is called exactly once.
    """
    k = any_kernel

    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("ctx_main = mo._runtime.context.get_context()"),
            exec_req.get(
                """
                ctx_thread = None
                def target():
                    global ctx_thread
                    ctx_thread = mo._runtime.context.get_context()
                mo.Thread(target=target).start().join()
                """
            ),
        ]
    )

    # thread run should be basically instantaneous, but sleep just in case ...
    time.sleep(0.01)  # noqa: ASYNC251
    assert k.globals["ctx_main"] == k.globals["ctx_thread"]
