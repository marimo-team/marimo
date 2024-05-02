from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

HAS_DEPS = DependencyManager.has_altair()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
async def test_altair(
    executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    from marimo._output.formatters.formatters import register_formatters

    register_formatters()

    await executing_kernel.run(
        [
            exec_req.get(
                """
                import altair as alt
                import pandas as pd
                from marimo._output.formatting import get_formatter

                data = pd.DataFrame({"a": ["A", "B"], "b": [28, 55]})
                chart = alt.Chart(data).mark_bar().encode(x="a", y="b")
                formatter = get_formatter(chart)
                result = formatter(chart)
                """
            )
        ]
    )

    result = executing_kernel.globals["result"]
    assert result is not None
    assert result[0] == "text/html"
    assert result[1].startswith("<iframe srcdoc=")
