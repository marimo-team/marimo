import time

from marimo._runtime.requests import DeleteCellRequest
from marimo._runtime.runtime import Kernel
from tests._messaging.mocks import MockStream
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
    """Test that a thread starts, runs, has its own stream."""

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


async def test_thread_output_append(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that a thread starts, runs, and appends to output."""

    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(
                """
                stream = mo._runtime.context.get_context().stream
                thread_stream = None
                def target():
                    global thread_stream
                    import marimo as mo
                    mo.output.append("hello")
                    mo.output.append("world")
                    thread_stream = mo._runtime.context.get_context().stream
                t = mo.Thread(target=target); t.start(); t.join()
                """
            ),
        ]
    )

    # thread run should be basically instantaneous, but sleep just in case ...
    assert not k.errors
    time.sleep(0.01)  # noqa: ASYNC251
    # The main thread should not have any output, but the new thread should
    cell_ops = MockStream(k.globals["stream"]).cell_ops
    for m in cell_ops:
        if m.output is not None:
            assert "hello" not in m.output.data
            assert "world" not in m.output.data
    thread_stream_cell_ops = MockStream(k.globals["thread_stream"]).cell_ops
    assert "hello" in thread_stream_cell_ops[0].output.data
    assert "world" in thread_stream_cell_ops[1].output.data


async def test_thread_print(k: Kernel, exec_req: ExecReqProvider) -> None:
    """Test that a thread starts, runs, and prints."""

    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(
                """
                stream = mo._runtime.context.get_context().stream
                thread_stream = None
                def target():
                    global thread_stream
                    import marimo as mo
                    print("hello")
                    print("world")
                    thread_stream = mo._runtime.context.get_context().stream
                t = mo.Thread(target=target); t.start(); t.join()
                """
            ),
        ]
    )

    # thread run should be basically instantaneous, but sleep just in case ...
    assert not k.errors
    time.sleep(0.01)  # noqa: ASYNC251
    # The main thread should not have any output, but the new thread should
    stream = MockStream(k.globals["stream"])
    for m in stream.operations:
        assert ("console" not in m) or not m["console"]

    thread_stream = MockStream(k.globals["thread_stream"])
    assert len(thread_stream.operations) == 2
    assert "hello" in thread_stream.operations[0]["console"]["data"]
    assert thread_stream.operations[0]["console"]["channel"] == "stdout"
    assert "world" in thread_stream.operations[1]["console"]["data"]
    assert thread_stream.operations[1]["console"]["channel"] == "stdout"


async def test_thread_should_exit_on_rerun(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that a thread's exit event is set when cell lifecycle is disposed."""

    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(
                """
                def target():
                    ...
                """
            ),
            er := exec_req.get(
                """
                thread = mo.Thread(target=target)
                thread.start()
                """
            ),
        ]
    )

    thread = k.globals["thread"]
    assert not thread.should_exit

    # rerunning the cell should trigger the cell lifecycle disposal and set its exit event
    await k.run([er])
    assert thread.should_exit


async def test_thread_should_not_exit_on_other_cell_run(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that a thread's exit event is set when cell lifecycle is disposed."""

    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(
                """
                def target():
                    ...
                """
            ),
            exec_req.get(
                """
                thread = mo.Thread(target=target)
                thread.start()
                """
            ),
            er := exec_req.get(
                """
                ...
                """
            ),
        ]
    )

    thread = k.globals["thread"]
    assert not thread.should_exit

    # rerunning a cell that is not related to the spawning cell should _not_
    # signal the thread to exit
    await k.run([er])
    assert not thread.should_exit


async def test_thread_should_exit_on_deletion(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that a thread's exit event is set when cell lifecycle is disposed."""

    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(
                """
                def target():
                    ...
                """
            ),
            er := exec_req.get(
                """
                thread = mo.Thread(target=target)
                thread.start()
                """
            ),
        ]
    )

    thread = k.globals["thread"]
    assert not thread.should_exit

    await k.delete_cell(DeleteCellRequest(er.cell_id))
    assert thread.should_exit
