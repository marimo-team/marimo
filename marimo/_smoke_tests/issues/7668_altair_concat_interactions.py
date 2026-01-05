import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import altair as alt
    import numpy as np
    import pyarrow
    import pandas as pd
    return alt, mo, np, pd


@app.cell
def _(alt, np, pd):
    source = pd.DataFrame({"x": np.random.rand(100), "y": np.random.rand(100)})

    brush = alt.selection_interval(encodings=["x"], value={"x": [0, 0.5]})

    base = (
        alt.Chart(source, width=600, height=200)
        .mark_area()
        .encode(x="x:Q", y="y:Q")
    )

    upper = base.encode(alt.X("x:Q").scale(domain=brush))

    lower = base.properties(height=60).add_params(brush)

    # Brush interaction across views works:
    upper & lower
    return lower, upper


@app.cell
def _(lower, mo, upper):
    # Brush interaction (no longer) breaks:
    mo.ui.altair_chart(upper & lower)
    return


@app.cell
def _(alt, lower, mo, upper):
    # Brush interaction works:
    mo.ui.altair_chart(alt.vconcat(upper & lower))
    return


if __name__ == "__main__":
    app.run()
