# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.altair_chart import VegaSpec, altair_chart


@dataclass
class Axis:
    label: Optional[str] = None


@dataclass
class LineChartArgs:
    x_column: str
    y_column: str
    x_axis: Axis
    y_axis: Axis


@dataclass
class BarChartArgs:
    x_column: str
    y_column: str
    x_axis: Axis
    y_axis: Axis


@dataclass
class PieChartArgs:
    x_column: str
    y_column: str
    x_axis: Axis
    y_axis: Axis


@dataclass
class PlotChartArgs:
    chart_type: str
    chart_args: Union[LineChartArgs, BarChartArgs, PieChartArgs]


@dataclass
class PlotChartResponse:
    # only altair supported atm
    spec: VegaSpec
    error: Optional[str] = None


def return_vega_spec() -> PlotChartResponse:
    if not DependencyManager.altair.has():
        return PlotChartResponse(
            spec="",
            error="Altair is not installed. Please install it with `pip install altair`.",
        )

    if not DependencyManager.polars.has():
        return PlotChartResponse(
            spec="",
            error="Polars is not installed. Please install it with `pip install polars`.",
        )

    import altair as alt
    import polars as pl

    try:
        df = pl.read_csv(
            "https://raw.githubusercontent.com/kirenz/datasets/b8f17b8fc4907748b3317554d65ffd780edcc057/gapminder.csv"
        )

        chart = (
            alt.Chart(df)
            .mark_point()
            .encode(
                x="continent",
                y="lifeExp",
                tooltip=["country", "lifeExp"],
                color="country",
            )
        )
        marimo_chart = altair_chart(
            chart, chart_selection=False, legend_selection=False
        )

        return PlotChartResponse(spec=marimo_chart._spec)
    except Exception as e:
        return PlotChartResponse(spec="", error=str(e))


def get_virtual_url(json_data: str) -> str:
    import base64
    import os
    import tempfile

    # Create a temporary file
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".json"
    ) as temp_file:
        temp_file.write(json_data.encode("utf-8"))
        temp_file_path = temp_file.name

    # Encode the file as base64
    with open(temp_file_path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")

    # Clean up the temporary file
    os.remove(temp_file_path)
