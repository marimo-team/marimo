import marimo

__generated_with = "0.9.21"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import altair as alt
    import pandas as pd

    # data
    test_counts = pd.DataFrame(
        [
            {"Level1": "a", "count": 1, "stage": "france"},
            {"Level1": "b", "count": 2, "stage": "france"},
            {"Level1": "c", "count": 3, "stage": "england"},
        ]
    )
    return alt, mo, pd, test_counts


@app.cell
def __(mo):
    mo.md(r"""## Layered""")
    return


@app.cell
def __(alt, mo, test_counts):
    # Base
    _base = alt.Chart(test_counts)

    # Params
    _point = alt.selection_point(encodings=["x"])
    _brush = alt.selection_interval(encodings=["x"])

    # Chart 1
    chart = (
        _base.mark_bar()
        .encode(
            x=alt.X("Level1").sort(order="descending").title("Subpillar"),
            y=alt.Y("count").title("Number of Companies"),
            color=alt.condition(_point, "stage", alt.value("lightgray")),
        )
        .add_params(_point, _brush)
    )

    # Chart 2
    rule = _base.mark_rule(strokeDash=[2, 2]).encode(
        y=alt.datum(2), color=alt.datum("england")
    )

    # Layered
    layered_chart = mo.ui.altair_chart(alt.layer(chart, rule))
    layered_chart
    return chart, layered_chart, rule


@app.cell
def __(layered_chart):
    layered_chart.value
    return


@app.cell
def __(mo):
    mo.md(r"""## Warnings""")
    return


@app.cell
def __(alt, chart, mo, rule):
    mo.ui.altair_chart(alt.layer(chart, rule), chart_selection="point")
    None
    return


if __name__ == "__main__":
    app.run()
