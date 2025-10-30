import marimo

__generated_with = "0.16.2"
app = marimo.App(width="full")


@app.cell
def _():
    from vega_datasets import data
    import altair as alt
    import marimo as mo

    cars = data.cars()

    _chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
        .properties(height=100)
    )
    return alt, cars, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## vconcat with hconcat inside""")
    return


@app.cell
def _(alt, cars):
    _chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
        .properties(height=100)
    )

    stacked_chart = alt.vconcat(
        alt.hconcat(
            _chart,
            _chart,
        ),
        _chart,
    )
    return (stacked_chart,)


@app.cell
def _(stacked_chart):
    stacked_chart
    return


@app.cell
def _(mo, stacked_chart):
    mo.ui.altair_chart(stacked_chart.copy())
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Nested vconcat""")
    return


@app.cell
def _(alt, cars):
    _chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
        .properties(height=100)
    )

    stacked_chart1 = alt.vconcat(
        _chart,
        alt.vconcat(
            _chart,
            _chart,
        ),
    )

    stacked_chart1
    return (stacked_chart1,)


@app.cell
def _(mo, stacked_chart1):
    mo.ui.altair_chart(stacked_chart1.copy())
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## hconcat with vconcat inside""")
    return


@app.cell
def _(alt, cars):
    _chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
        .properties(height=100)
    )

    h_v_chart = alt.hconcat(
        alt.vconcat(
            _chart,
            _chart,
        ),
        _chart,
    )

    h_v_chart
    return (h_v_chart,)


@app.cell
def _(h_v_chart, mo):
    mo.ui.altair_chart(h_v_chart.copy())
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Nested hconcat""")
    return


@app.cell
def _(alt, cars):
    _chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
        .properties(height=100)
    )

    nested_h_chart = alt.hconcat(
        _chart,
        alt.hconcat(
            _chart,
            _chart,
        ),
    )

    nested_h_chart
    return (nested_h_chart,)


@app.cell
def _(mo, nested_h_chart):
    mo.ui.altair_chart(nested_h_chart.copy())
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Complex nested combination""")
    return


@app.cell
def _(alt, cars):
    _chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
        .properties(height=100)
    )

    # Complex: vconcat(hconcat(vconcat(...), ...), ...)
    complex_chart = alt.vconcat(
        alt.hconcat(
            alt.vconcat(
                _chart,
                _chart,
            ),
            _chart,
        ),
        alt.hconcat(
            _chart,
            _chart,
        ),
    )

    complex_chart
    return (complex_chart,)


@app.cell
def _(complex_chart, mo):
    mo.ui.altair_chart(complex_chart.copy())
    return


if __name__ == "__main__":
    app.run()
