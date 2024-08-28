# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "plotly",
# ]
# ///

import marimo

__generated_with = "0.8.3"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import plotly.io as pio
    import plotly.graph_objects as go

    print("default theme:", pio.templates.default)
    return go, mo, pio


@app.cell
def __(go, pio):
    pio.templates.default = "plotly_white"

    go.Figure(
        data=[go.Bar(y=[2, 1, 3])],
    )
    return


@app.cell
def __(go, pio):
    pio.templates.default = "plotly"

    go.Figure(
        data=[go.Bar(y=[2, 1, 3])],
    )
    return


@app.cell
def __(go, pio):
    pio.templates.default = "plotly_dark"

    go.Figure(
        data=[go.Bar(y=[2, 1, 3])],
    )
    return


if __name__ == "__main__":
    app.run()
