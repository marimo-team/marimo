# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.8"
app = marimo.App(layout_file="layouts/grid.grid.json")


@app.cell
def __(mo):
    align = mo.ui.dropdown(
        label="Align", options=["start", "end", "center", "stretch"]
    )
    justify = mo.ui.dropdown(
        label="Justify",
        options=["start", "center", "end", "space-between", "space-around"],
    )
    gap = mo.ui.number(label="Gap", start=0, stop=100, value=1)
    size = mo.ui.slider(label="Size", start=60, stop=500)
    wrap = mo.ui.checkbox(label="Wrap")

    mo.hstack([align, justify, gap, size, wrap], gap=0.25)
    return align, gap, justify, size, wrap


@app.cell
def __(mo):
    mo.md("# Horizontal Stack: `hstack`")
    return


@app.cell
def __(align, boxes, gap, justify, mo, wrap):
    mo.hstack(
        boxes,
        align=align.value,
        justify=justify.value,
        gap=gap.value,
        wrap=wrap.value,
    )
    return


@app.cell
def __(mo):
    mo.md("# Vertical Stack: `vstack`")
    return


@app.cell
def __(align, boxes, gap, mo):
    mo.vstack(
        boxes,
        align=align.value,
        gap=gap.value,
    )
    return


@app.cell
def __(mo, size):
    def create_box(num):
        box_size = size.value + num * 10
        return mo.Html(
            f"<div style='min-width: {box_size}px; min-height: {box_size}px; background-color: orange; text-align: center; line-height: {box_size}px'>{str(num)}</div>"
        )


    boxes = [create_box(i) for i in range(1, 5)]
    return boxes, create_box


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
