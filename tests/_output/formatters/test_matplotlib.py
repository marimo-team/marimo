from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.runtime.kernel import Kernel
from tests.conftest import ExecReqProvider

HAS_MPL = DependencyManager.matplotlib.has()


@pytest.mark.skipif(not HAS_MPL, reason="optional dependencies not installed")
async def test_matplotlib_rc_light(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    import matplotlib.pyplot as plt  # type: ignore

    from marimo._output.formatters.formatters import register_formatters

    plt.rcParams["font.family"] = ["monospace"]

    register_formatters(theme="light")

    await executing_kernel.run(
        [
            exec_req.get(
                """
                import matplotlib.pyplot as plt

                rcParams = plt.rcParams
                """
            )
        ]
    )

    rcParams = executing_kernel.globals["rcParams"]
    assert rcParams["font.family"] == ["monospace"]
    assert rcParams["figure.facecolor"] == "white"


@pytest.mark.skipif(not HAS_MPL, reason="optional dependencies not installed")
async def test_matplotlib_rc_dark(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    import matplotlib.pyplot as plt  # type: ignore

    from marimo._output.formatters.formatters import register_formatters

    plt.rcParams["font.family"] = ["monospace"]

    register_formatters(theme="dark")

    await executing_kernel.run(
        [
            exec_req.get(
                """
                import matplotlib.pyplot as plt

                rcParams = plt.rcParams
                """
            )
        ]
    )

    rcParams = executing_kernel.globals["rcParams"]
    assert rcParams["font.family"] == ["monospace"]
    assert rcParams["figure.facecolor"] == "black"
