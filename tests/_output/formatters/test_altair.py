from __future__ import annotations

import json

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

HAS_ALTAIR = DependencyManager.altair.has()
HAS_VL_CONVERT = DependencyManager.has("vl-convert")


@pytest.mark.skipif(
    not HAS_ALTAIR, reason="optional dependencies not installed"
)
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
    assert result[0] == "application/vnd.vegalite.v5+json"
    # Valid JSON
    assert "$schema" in result[1]
    assert isinstance(result[1], str)
    assert json.loads(result[1])


@pytest.mark.skipif(
    not HAS_ALTAIR, reason="optional dependencies not installed"
)
async def test_altair_with_embed_options(
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

                before_options_result = formatter(chart)
                alt.renderers.set_embed_options(actions=False)
                after_options_result = formatter(chart)
                """
            )
        ]
    )

    result = executing_kernel.globals["before_options_result"]
    assert result is not None
    assert result[0] == "application/vnd.vegalite.v5+json"
    json_result = json.loads(result[1])
    assert json_result["usermeta"] == {
        "embedOptions": {},
    }

    result = executing_kernel.globals["after_options_result"]
    assert result is not None
    assert result[0] == "application/vnd.vegalite.v5+json"
    json_result = json.loads(result[1])
    assert json_result["usermeta"] == {
        "embedOptions": {
            "actions": False,
        },
    }


@pytest.mark.skipif(
    not HAS_ALTAIR or not HAS_VL_CONVERT,
    reason="optional dependencies not installed and fails on mac",
)
async def test_altair_with_svg(
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
                alt.renderers.enable("svg")
                chart = alt.Chart(data).mark_bar().encode(x="a", y="b")
                formatter = get_formatter(chart)
                result = formatter(chart)
                """
            )
        ]
    )

    result = executing_kernel.globals["result"]
    assert result is not None
    assert result[0] == "image/svg+xml"
    assert result[1].startswith("<svg")


# TODO: Add tests for vegafusion
