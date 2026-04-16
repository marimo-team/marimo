# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "altair==6.0.0",
#     "vl-convert-python",
#     "pandas==3.0.2",
# ]
# ///
# Repro for https://github.com/marimo-team/marimo/issues/9015
# and https://github.com/marimo-team/marimo/issues/9013

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo
    import altair as alt
    import pandas as pd

    # Verify vl-convert-python is installed; it's required for the SVG renderer.
    import vl_convert as vlc


@app.cell
def _():
    data = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [2, 7, 4, 8, 5]})
    return (data,)


@app.cell
def _(data):
    alt.renderers.enable("svg")

    chart = alt.Chart(data).mark_point().encode(x="x", y="y")
    return (chart,)


@app.cell
def _(chart):
    # This works
    chart
    return


@app.cell
def _(chart):
    # SVG outputs should be correctly rendered in vstack or hstack
    # (reported in Issue #9015 and fixed in PR #9043).
    # For vstack, align="start" is needed to preserve the image size
    mo.vstack([chart], align="start")
    return


@app.cell
def _(data):
    # Issue #9013: SVG rendering breaks image marks
    chart_with_images = (
        alt.Chart(data)
        .mark_image(
            url="https://vega.github.io/vega-datasets/data/ffox.png",
            width=50,
            height=50,
        )
        .encode(
            x="x",
            y="y",
        )
    )
    return (chart_with_images,)


@app.cell
def _(chart_with_images):
    # This works
    alt.renderers.enable("default")
    chart_with_images
    return


@app.cell
def _(chart_with_images):
    # Image marks are broken.
    # The root cause is the browser's security restriction.
    # When marimo detects an SVG with external resources (e.g., image URLs),
    # it warns the user to enable 'raw_svg=True' for correct rendering.
    alt.renderers.enable("svg")
    chart_with_images
    return


@app.cell
def _(chart_with_images):
    # Image marks are correctly rendered when 'raw_svg=True' is enabled.
    alt.renderers.enable("svg", raw_svg=True)
    chart_with_images
    return


if __name__ == "__main__":
    app.run()
