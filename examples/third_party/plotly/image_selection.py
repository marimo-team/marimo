# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
#     "pandas",
#     "plotly==5.24.1",
#     "scikit-image",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import plotly.graph_objects as go
    import plotly.express as px
    from skimage import io

    return go, io, mo, px


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    #Example: Image with range selection
    """)
    return


@app.cell
def _(io, mo, px):
    # Create figure
    img = io.imread("https://marimo.io/logo.png")
    _fig = px.imshow(img)
    _fig.update_layout(template="plotly_white")

    # Wrap with marimo
    plot = mo.ui.plotly(_fig)
    return (plot,)


@app.cell
def _(mo, plot):
    mo.hstack(
        [
            plot,
            {
                "plot.ranges": plot.ranges,
                "plot.value": plot.value,
                "plot.indcides": plot.indices,
            },
        ]
    )
    return


@app.cell
def _(mo):
    mo.md("""
    #Example: Image with overlaid trace
    """)
    return


@app.cell
def _(go, mo):
    # Create figure
    _fig = go.Figure()

    # Add trace
    _fig.add_trace(go.Scatter(x=[0, 0.5, 1, 2, 2.2], y=[1.23, 2.5, 0.42, 3, 1]))

    # Add images
    _fig.add_layout_image(
        dict(
            source="https://marimo.io/logo.png",
            xref="x",
            yref="y",
            x=0,
            y=3,
            sizex=2,
            sizey=2,
            opacity=0.8,
            layer="below",
        )
    )

    # Set templates
    _fig.update_layout(template="plotly_white")
    plot2 = mo.ui.plotly(_fig)
    return (plot2,)


@app.cell
def _(mo, plot2):
    mo.hstack(
        [
            plot2,
            {
                "plot.ranges": plot2.ranges,
                "plot.value": plot2.value,
                "plot.indcides": plot2.indices,
            },
        ]
    )
    return


if __name__ == "__main__":
    app.run()
