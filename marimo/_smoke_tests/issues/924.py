# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="full")


@app.cell
def _(mo):
    mo.md(
        """
    # Scrollbar issue with iframed altair

    There should be no vertical scrollbar within the iframed container.

    """
    )
    return


@app.cell
def _():
    import micropip
    import altair as alt

    import marimo as mo
    import numpy as np
    import pandas as pd

    np.random.seed(11)
    N = 100
    x = np.linspace(0, 300, num=N)
    y = np.linspace(0, 300, num=N)

    df = pd.DataFrame({"x": x, "y": y})

    graph = (
        alt.Chart(df)
        .mark_circle()
        .encode(
            x="x:Q",
            y="y:Q",
        )
        .properties(width=1820, height=780)
    )
    graph
    return (mo,)


if __name__ == "__main__":
    app.run()
