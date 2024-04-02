# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.2"
app = marimo.App(width="full")


@app.cell
def __(mo):
    mo.md(
        """
    # Scrollbar issue with iframed altair

    There should be no vertical scrollbar within the iframed container.
          
    """
    )
    return


@app.cell
def __():
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
    return N, alt, df, graph, micropip, mo, np, pd, x, y


if __name__ == "__main__":
    app.run()
