import marimo

__generated_with = "0.17.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import altair as alt
    import pandas as pd
    import marimo as mo
    return alt, mo, pd


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ## Composite Chart Legend Selection Bug

    Test case for https://github.com/marimo-team/marimo/issues/6676

    Legend selection should work on composite charts created with the `+` operator.
    Clicking legend items should filter the chart.
    """
    )
    return


@app.cell
def _(pd):
    sample_data = [
        [2, 1, 4, 10, "a"],
        [3, 0, 6, 12, "b"],
        [8, 5, 12, 15, "c"],
    ]
    sample_df = pd.DataFrame(
        sample_data, columns=["value", "lower", "upper", "x_value", "category"]
    )
    sample_df
    return (sample_df,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### Composite chart with error bars and points""")
    return


@app.cell
def _(alt, mo, sample_df):
    sample_color = alt.Color(
        field="category",
        type="nominal",
        legend=alt.Legend(
            title="category",
            labelLimit=0,
            symbolLimit=0,
        ),
    )

    sample_base_chart = alt.Chart(sample_df, title="Sample Error Bars")

    sample_rule = sample_base_chart.mark_rule().encode(
        x=alt.X("x_value"),
        y=alt.Y("upper"),
        y2="lower",
        color=sample_color,
    )

    sample_upper_tick = sample_base_chart.mark_tick(
        orient="horizontal", size=5
    ).encode(
        x="x_value:Q",
        y="upper:Q",
        color=sample_color,
    )
    sample_tick = sample_upper_tick.encode(y="lower:Q")

    sample_lines = sample_rule + sample_upper_tick + sample_tick

    sample_dots = sample_base_chart.mark_point(filled=True, size=60).encode(
        x=alt.X("x_value"),
        y=alt.Y("value"),
        color=sample_color,
    )

    alt_chart = sample_dots + sample_lines

    sample_mo_chart = mo.ui.altair_chart(alt_chart)

    sample_mo_chart
    return (sample_mo_chart,)


@app.cell
def _(sample_mo_chart):
    sample_mo_chart.value
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### Simple layered chart (for comparison)""")
    return


@app.cell
def _(alt, mo, pd):
    # Create a simple layered chart to compare
    simple_data = pd.DataFrame(
        {
            "x": [1, 2, 3, 4, 5] * 3,
            "y": [1, 2, 3, 4, 5, 2, 3, 4, 5, 6, 3, 4, 5, 6, 7],
            "category": ["A"] * 5 + ["B"] * 5 + ["C"] * 5,
        }
    )

    simple_chart = alt.Chart(simple_data).mark_line().encode(
        x="x:Q", y="y:Q", color="category:N"
    ) + alt.Chart(simple_data).mark_point(size=100).encode(
        x="x:Q", y="y:Q", color="category:N"
    )

    simple_mo_chart = mo.ui.altair_chart(simple_chart)
    simple_mo_chart
    return (simple_mo_chart,)


@app.cell
def _(simple_mo_chart):
    simple_mo_chart.value
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### Workaround with explicit legend selection""")
    return


@app.cell
def _(alt, mo, sample_df):
    # Workaround from the issue: explicit legend selection
    legend_select = alt.selection_point(fields=["category"], bind="legend")

    workaround_color = alt.Color(
        field="category",
        type="nominal",
        legend=alt.Legend(
            title="category",
            labelLimit=0,
            symbolLimit=0,
        ),
    )

    workaround_base = alt.Chart(
        sample_df, title="Workaround with Explicit Selection"
    )

    workaround_rule = (
        workaround_base.mark_rule()
        .encode(
            x=alt.X("x_value"),
            y=alt.Y("upper"),
            y2="lower",
            color=workaround_color,
            opacity=alt.condition(legend_select, alt.value(1), alt.value(0.2)),
        )
        .add_params(legend_select)
    )

    workaround_dots = (
        workaround_base.mark_point(filled=True, size=60)
        .encode(
            x=alt.X("x_value"),
            y=alt.Y("value"),
            color=workaround_color,
            opacity=alt.condition(legend_select, alt.value(1), alt.value(0.2)),
        )
        .add_params(legend_select)
    )

    workaround_chart = workaround_dots + workaround_rule

    workaround_mo_chart = mo.ui.altair_chart(
        workaround_chart, chart_selection=None, legend_selection="legend_select"
    )
    workaround_mo_chart
    return (workaround_mo_chart,)


@app.cell
def _(workaround_mo_chart):
    workaround_mo_chart.value
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### vconcat with legend selection""")
    return


@app.cell
def _(alt, mo, pd):
    # Test vconcat with same color field
    vconcat_data = pd.DataFrame({
        'x': list(range(10)) * 3,
        'y': list(range(10)) + list(range(5, 15)) + list(range(10, 20)),
        'category': ['A'] * 10 + ['B'] * 10 + ['C'] * 10
    })

    vconcat_chart = alt.vconcat(
        alt.Chart(vconcat_data).mark_point().encode(
            x='x:Q',
            y='y:Q',
            color='category:N'
        ),
        alt.Chart(vconcat_data).mark_bar().encode(
            x='category:N',
            y='mean(y):Q',
            color='category:N'
        )
    )

    vconcat_mo_chart = mo.ui.altair_chart(vconcat_chart)
    vconcat_mo_chart
    return (vconcat_mo_chart,)


@app.cell
def _(vconcat_mo_chart):
    vconcat_mo_chart.value
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### hconcat with legend selection""")
    return


@app.cell
def _(alt, mo, pd):
    # Test hconcat with same color field
    hconcat_data = pd.DataFrame({
        'x': list(range(10)) * 3,
        'y': list(range(10)) + list(range(5, 15)) + list(range(10, 20)),
        'series': ['X'] * 10 + ['Y'] * 10 + ['Z'] * 10
    })

    hconcat_chart = alt.hconcat(
        alt.Chart(hconcat_data).mark_line().encode(
            x='x:Q',
            y='y:Q',
            color='series:N'
        ),
        alt.Chart(hconcat_data).mark_point(size=100).encode(
            x='x:Q',
            y='y:Q',
            color='series:N'
        )
    )

    hconcat_mo_chart = mo.ui.altair_chart(hconcat_chart)
    hconcat_mo_chart
    return (hconcat_mo_chart,)


@app.cell
def _(hconcat_mo_chart):
    hconcat_mo_chart.value
    return


if __name__ == "__main__":
    app.run()
