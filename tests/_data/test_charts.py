from __future__ import annotations

import ast
from typing import List

import pytest

from marimo._data.charts import ChartBuilder, get_chart_builder
from marimo._data.models import DataType
from marimo._dependencies.dependencies import DependencyManager
from tests.mocks import snapshotter

TYPES: List[DataType] = [
    "boolean",
    "date",
    "integer",
    "number",
    "string",
    "unknown",
]

snapshot = snapshotter(__file__)

HAS_DEPS = DependencyManager.has_pandas() and DependencyManager.has_altair()


def test_get_chart_builder():
    for t in TYPES:
        assert isinstance(get_chart_builder(t), ChartBuilder)


def test_charts_altair_code():
    outputs: List[str] = []

    for t in TYPES:
        builder = get_chart_builder(t)
        code = builder.altair_code("df", "some_column")
        # Validate it is valid Python code
        try:
            ast.parse(code)
        except SyntaxError as e:
            raise SyntaxError(f"Invalid Python code for {t}") from e
        outputs.append(f"# {t}\n{code}")

    snapshot("charts.txt", "\n\n".join(outputs))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_charts_altair_json():
    outputs: List[str] = []
    import altair as alt
    import pandas as pd

    data = pd.DataFrame({"some_column": [1, 2, 3]})

    for t in TYPES:
        builder = get_chart_builder(t)
        code = builder.altair_json(data, "some_column")
        # Validate it is valid JSON
        alt.Chart.from_json(code)
        outputs.append(f"# {t}\n{code}")

    snapshot("charts_json.txt", "\n\n".join(outputs))
