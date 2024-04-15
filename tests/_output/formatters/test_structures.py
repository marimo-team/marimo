from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


async def test_matplotlib_special_case(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    if DependencyManager.has_matplotlib() and DependencyManager.has_numpy():
        from marimo._output.formatters.formatters import register_formatters

        register_formatters()

        await executing_kernel.run(
            [
                exec_req.get(
                    """
                    import numpy as np
                    import matplotlib.pyplot as plt
                    from marimo._output.formatting import get_formatter

                    arr = np.random.randn(12, 5)
                    lines = plt.plot(arr)
                    formatter = get_formatter(lines)
                    """
                )
            ]
        )

        formatter = executing_kernel.globals["formatter"]
        lines = executing_kernel.globals["lines"]
        assert formatter is not None
        assert formatter(lines)[0].startswith("image")
