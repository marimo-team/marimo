from __future__ import annotations

from typing import Any, List, cast

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.structures import format_structure
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


async def test_matplotlib_special_case(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    if DependencyManager.matplotlib.has() and DependencyManager.numpy.has():
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


def test_format_structure_types() -> None:
    formatted = cast(
        List[Any], format_structure(["hello", True, False, None, 1, 1.0])
    )
    assert formatted[0] == 'text/plain:"hello"'
    assert formatted[1] is True
    assert formatted[2] is False
    assert formatted[3] is None
    assert formatted[4] == "text/plain:1"
    assert formatted[5] == "text/plain:1.0"
