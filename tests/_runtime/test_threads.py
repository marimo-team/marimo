import time

from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


# Doesn't work with strict kernel ...
async def test_thread_set_global(k: Kernel, exec_req: ExecReqProvider) -> None:
    """Test that a thread starts and runs."""

    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(
                """
                value = 0
                def target():
                    global value
                    value = 1
                """
            ),
            exec_req.get("t = mo.Thread(target=target); t.start(); t.join()"),
        ]
    )

    # thread run should be basically instantaneous, but sleep just in case ...
    assert not k.errors
    time.sleep(0.01)  # noqa: ASYNC251
    assert k.globals["value"] == 1


async def test_thread_has_own_stream(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that a thread starts and runs."""

    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("ctx_main = mo._runtime.context.get_context()"),
            exec_req.get(
                """
                cell_id = ctx_main.stream.cell_id
                thread_ctx = None
                def target():
                    global thread_ctx
                    thread_ctx = mo._runtime.context.get_context()
                t = mo.Thread(target=target); t.start(); t.join()
                """
            ),
        ]
    )

    # thread run should be basically instantaneous, but sleep just in case ...
    assert not k.errors
    time.sleep(0.01)  # noqa: ASYNC251
    # thread gets its own context
    assert k.globals["thread_ctx"] != k.globals["ctx_main"]
    stream = k.globals["thread_ctx"].stream
    assert stream.cell_id == k.globals["cell_id"]
