from __future__ import annotations

import ast

import pytest

from marimo._data.charts import ChartBuilder, get_chart_builder
from marimo._data.models import DataType
from marimo._dependencies.dependencies import DependencyManager
from tests.mocks import snapshotter

TYPES: list[tuple[DataType, bool]] = [
    ("boolean", False),
    ("date", False),
    ("datetime", False),
    ("time", False),
    ("integer", False),
    ("number", False),
    ("string", False),
    ("string", True),
    ("unknown", False),
]

snapshot = snapshotter(__file__)

HAS_DEPS = DependencyManager.pandas.has() and DependencyManager.altair.has()


def test_get_chart_builder():
    for t, should_limit_to_10_items in TYPES:
        assert isinstance(
            get_chart_builder(t, should_limit_to_10_items), ChartBuilder
        )


def test_charts_altair_code():
    outputs: list[str] = []

    for t, should_limit_to_10_items in TYPES:
        builder = get_chart_builder(t, should_limit_to_10_items)
        code = builder.altair_code("df", "some_column")
        # Validate it is valid Python code
        try:
            ast.parse(code)
        except SyntaxError as e:
            raise SyntaxError(f"Invalid Python code for {t}") from e
        title = f"{t} (limit to 10 items)" if should_limit_to_10_items else t
        outputs.append(f"# {title}\n{code}")

    snapshot("charts.txt", "\n\n".join(outputs))


def test_charts_bad_characters():
    outputs: list[str] = []
    builder = get_chart_builder("string", False)
    chars = {
        "<": "angles",
        "[0]": "brackets",
        ":": "colon",
        ".": "period",
        "\\": "backslash",
    }

    for char, name in chars.items():
        col = f"col{char}{name}"
        code = builder.altair_code("df", col)
        outputs.append(f"# {col}\n{code}")

    snapshot("charts_bad_characters.txt", "\n\n".join(outputs))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_charts_altair_json():
    outputs: list[str] = []
    import altair as alt
    import pandas as pd

    data = pd.DataFrame({"some_column": [1, 2, 3]})

    for t, should_limit_to_10_items in TYPES:
        builder = get_chart_builder(t, should_limit_to_10_items)
        code = builder.altair_json(data, "some_column")
        # Validate it is valid JSON
        alt.Chart.from_json(code)
        title = f"{t} (limit to 10 items)" if should_limit_to_10_items else t
        outputs.append(f"# {title}\n{code}")

    snapshot("charts_json.txt", "\n\n".join(outputs))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_charts_altair_json_bad_data():
    import altair as alt
    import pandas as pd

    data = pd.DataFrame({"some[0]really.bad:column": [1, 2, 3]})

    build = get_chart_builder("string", False)
    code = build.altair_json(data, "some[0]really.bad:column")
    # Validate it is valid JSON
    alt.Chart.from_json(code)
    snapshot("charts_json_bad_data.txt", code)
