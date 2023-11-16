# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.conftest import ExecReqProvider, MockedKernel


def test_spinner_removed(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    mocked_kernel.k.run(
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
