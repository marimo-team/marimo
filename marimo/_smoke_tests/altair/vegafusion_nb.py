# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "altair",
#     "marimo",
#     "vegafusion",
# ]
# ///

import marimo

__generated_with = "0.8.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md(r"""# Basic examples""")
    return


@app.cell
def __():
    import pandas as pd
    import altair as alt
    import vegafusion as vf

    # Comment out to disable duckdb connection
    vf.runtime.set_connection("duckdb")

    flights = pd.read_parquet(
        "https://vegafusion-datasets.s3.amazonaws.com/vega/flights_1m.parquet"
    )
    return alt, flights, pd, vf


@app.cell
def __(alt, flights, mo):
    delay_hist = (
        alt.Chart(flights)
        .mark_bar()
        .encode(alt.X("delay", bin=alt.Bin(maxbins=30)), alt.Y("count()"))
    )

    with alt.data_transformers.enable("vegafusion"):
        mo.output.replace(delay_hist)
    return delay_hist,


@app.cell
def __(alt, delay_hist, mo):
    alt.data_transformers.enable("vegafusion")
    mo.as_html(delay_hist)
    return


@app.cell
def __(alt, delay_hist):
    alt.data_transformers.enable("vegafusion")
    delay_hist
    return


@app.cell
def __(alt, delay_hist, mo):
    alt.data_transformers.enable("vegafusion")
    mo.ui.altair_chart(delay_hist)
    return


@app.cell
def __(alt, delay_hist, mo):
    # This should throw an error
    try:
        alt.data_transformers.enable("default")
        mo.output.replace(delay_hist)
        mo.output.replace("No error found")
    except Exception as e:
        print(e)
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        # Examples from vegafusion

        The examples below still hit `MARIMO_OUTPUT_MAX_BYTES` limitations, and require increasing this before running this notebook:

        ```
        export MARIMO_OUTPUT_MAX_BYTES=100_000_000
        ```
        """
    )
    return


@app.cell
def __(mo):
    mo.md(r"""## Interactive Cross-filter""")
    return


@app.cell
def __(alt):
    def make_cross_filter_chart(source):
        brush = alt.selection_interval(encodings=["x"])

        # Define the base chart, with the common parts of the
        # background and highlights
        base = (
            alt.Chart()
            .mark_bar()
            .encode(
                x=alt.X(
                    alt.repeat("column"),
                    type="quantitative",
                    bin=alt.Bin(maxbins=20),
                ),
                y="count()",
            )
            .properties(width=160, height=130)
        )

        # gray background with selection
        background = base.encode(color=alt.value("#ddd")).add_params(brush)

        # blue highlights on the transformed data
        highlight = base.transform_filter(brush)

        # layer the two charts & repeat
        return (
            alt.layer(background, highlight, data=source)
            .transform_calculate("time", "hours(datum.date)")
            .repeat(column=["distance", "delay", "time"])
        )
    return make_cross_filter_chart,


@app.cell
def __(alt, make_cross_filter_chart, pd):
    alt.data_transformers.enable("vegafusion")
    source_data = pd.read_parquet(
        "https://vegafusion-datasets.s3.amazonaws.com/vega/flights_200k.parquet"
    )
    make_cross_filter_chart(source_data)
    return source_data,


@app.cell
def __(mo):
    mo.md(r"""## Interactive average""")
    return


@app.cell
def __(alt):
    def make_average_chart(source):
        brush = alt.selection_interval(encodings=["x"])

        bars = (
            alt.Chart()
            .mark_bar()
            .encode(
                x="utcmonth(date):O",
                y="mean(precipitation):Q",
                opacity=alt.condition(
                    brush, alt.OpacityValue(1), alt.OpacityValue(0.7)
                ),
            )
            .add_params(brush)
        )

        line = (
            alt.Chart()
            .mark_rule(color="firebrick")
            .encode(y="mean(precipitation):Q", size=alt.SizeValue(3))
            .transform_filter(brush)
        )

        return alt.layer(bars, line, data=source).properties(height=200)
    return make_average_chart,


@app.cell
def __(alt, make_average_chart, pd):
    alt.data_transformers.enable("vegafusion")
    _source_data = pd.read_parquet(
        "https://vegafusion-datasets.s3.amazonaws.com/vega/seattle_weather_200k.parquet"
    )
    make_average_chart(_source_data)
    return


@app.cell
def __(mo):
    mo.md(r"""## Interactive Chart with Cross-Highlight""")
    return


@app.cell
def __(alt):
    def make_movie_chart(data_source):
        pts = alt.selection_point(encodings=["x"])

        rect = (
            alt.Chart(data_source)
            .mark_rect()
            .encode(
                alt.X("IMDB_Rating:Q", bin=True),
                alt.Y("Rotten_Tomatoes_Rating:Q", bin=True),
                alt.Color(
                    "count()",
                    scale=alt.Scale(scheme="greenblue"),
                    legend=alt.Legend(title="Total Records"),
                ),
            )
        )

        circ = (
            rect.mark_point()
            .encode(
                alt.ColorValue("grey"),
                alt.Size(
                    "count()", legend=alt.Legend(title="Records in Selection")
                ),
            )
            .transform_filter(pts)
            .properties(width=300, height=250)
        )

        bar = (
            alt.Chart(data_source)
            .mark_bar()
            .encode(
                x="Major_Genre:N",
                y="count()",
                color=alt.condition(
                    pts, alt.ColorValue("steelblue"), alt.ColorValue("grey")
                ),
            )
            .properties(width=300, height=250)
            .add_params(pts)
        )

        return alt.hconcat(
            bar,
            rect + circ,
        ).resolve_legend(color="independent", size="independent")
    return make_movie_chart,


@app.cell
def __(alt, make_movie_chart, pd):
    alt.data_transformers.enable("vegafusion")
    _source_data = pd.read_parquet(
        "https://vegafusion-datasets.s3.amazonaws.com/vega/movies_201k.parquet"
    )
    make_movie_chart(_source_data)
    return


@app.cell
def __(mo):
    mo.md(r"""# Vega fusion mimes""")
    return


@app.cell
def __(alt, flights, vf):
    vf.enable(mimetype="html")
    alt.data_transformers.enable("vegafusion")
    alt.Chart(flights).mark_bar().encode(
        alt.X("delay", bin=alt.Bin(maxbins=30)), alt.Y("count()")
    )
    return


@app.cell
def __(alt, flights, vf):
    vf.enable(mimetype="svg")
    alt.Chart(flights).mark_bar().encode(
        alt.X("delay", bin=alt.Bin(maxbins=30)), alt.Y("count()")
    )
    return


@app.cell
def __(alt, flights, vf):
    vf.enable(mimetype="vega")
    alt.Chart(flights).mark_bar().encode(
        alt.X("delay", bin=alt.Bin(maxbins=30)), alt.Y("count()")
    )
    return


@app.cell
def __(alt, flights, vf):
    vf.enable(mimetype="png")
    alt.Chart(flights).mark_bar().encode(
        alt.X("delay", bin=alt.Bin(maxbins=30)), alt.Y("count()")
    )
    return


if __name__ == "__main__":
    app.run()
