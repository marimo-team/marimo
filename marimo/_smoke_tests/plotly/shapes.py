import marimo

__generated_with = "0.19.5"
app = marimo.App(width="medium", auto_download=["html"])


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import plotly.express as px
    import numpy as np
    return np, px


@app.cell
def _(mo):
    plot_boxes = mo.ui.checkbox(label="Plot boxes", value=False)
    return (plot_boxes,)


@app.cell
def _(plot_boxes):
    plot_boxes
    return


@app.cell
def _(np, plot_boxes, px):
    img_rgb = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255]],
                        [[0, 255, 0], [0, 0, 255], [255, 0, 0]]
                       ], dtype=np.uint8)
    fig = px.imshow(img_rgb)
    if plot_boxes.value:
        fig.add_shape(type="rect",
            xref="paper", yref="paper",
            x0=0.4, y0=0.4,
            x1=0.6, y1=0.6,
            line=dict(
                color="Red",
                width=3,
            )
        )
    fig.update_layout(
        dragmode='drawrect',
        newshape=dict(line_color='cyan'))
    fig
    return (fig,)


@app.cell
def _(fig):
    fig.layout.shapes
    return


if __name__ == "__main__":
    app.run()
