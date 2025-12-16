import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import matplotlib.pyplot as plt
    return (plt,)


@app.cell
def _(plt):
    import numpy as np

    plt.hist(np.random.rand(1000), bins=10)
    return


@app.cell
def _():
    import altair as alt

    chart = (
        alt.Chart(
            alt.Data(
                values=[
                    {"x": 1, "y": 5, "category": "A"},
                    {"x": 2, "y": 8, "category": "B"},
                ]
            )
        )
        .mark_circle(size=100)
        .encode(x="x:Q", y="y:Q")
    )

    [chart, "application/foo:bar"]
    return


if __name__ == "__main__":
    app.run()
