# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from tests.conftest import ExecReqProvider, MockedKernel


async def test_spinner_removed(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    await mocked_kernel.k.run(
        [
            exec_req.get(
                """
                import marimo as mo

                with mo.status.spinner():
                    ...
                123
                """
            )
        ]
    )
    found_progress = False
    for i, msg in enumerate(mocked_kernel.stream.messages):
        if (
            msg[0] == "cell-op"
            and msg[1]["output"] is not None
            and "marimo-progress" in msg[1]["output"]["data"]
        ):
            # the spinner should be cleared immediately after the context
            # manager exits
            found_progress = True
            # kernel uses text/plain + empty string to denote empty output
            assert (
                mocked_kernel.stream.messages[i + 1][1]["output"]["data"] == ""
            )
    assert found_progress


async def test_mutating_appended_outputs(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    # append the same object multiple times, but mutate it in between
    # appends. make sure the final output message contains the both
    # versions of the object (before and after mutation)
    await mocked_kernel.k.run(
        [
            exec_req.get(
                """
                import marimo as mo

                x = ["before"]
                mo.output.append(x)
                x[0] = "after"
                mo.output.append(x)
                """
            )
        ]
    )
    outputs: list[str] = []
    for msg in mocked_kernel.stream.messages:
        if msg[0] == "cell-op" and msg[1]["output"] is not None:
            outputs.append(msg[1]["output"]["data"])
    assert len(outputs) == 2
    assert "before" in outputs[0]
    assert "before" in outputs[1]
    assert "after" in outputs[1]
