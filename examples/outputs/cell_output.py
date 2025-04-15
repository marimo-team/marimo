# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "matplotlib==3.10.1",
# ]
# ///

import marimo

__generated_with = "0.12.9"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        The last expression of a cell is its visual output. This output
        appears above the cell when editing a notebook, with notebook code
        serving as a "caption" for the output. Outputs can be configured
        to appear below cells in the user settings.

        If running
        a notebook as an app, the output is the visual representation
        of the cell (code is hidden by default).
        """
    )
    return


@app.cell
def _(plt):
    def draw_fractal(ax, levels=4, x=0, y=0, size=1):
        if levels == 0:
            ax.add_patch(plt.Rectangle((x, y), size, size, color="navy"))
        else:
            size3 = size / 3
            for i in range(3):
                for j in range(3):
                    if (i + j) % 2 == 0:
                        draw_fractal(
                            ax, levels - 1, x + i * size3, y + j * size3, size3
                        )


    fig, ax = plt.subplots()
    ax.set_aspect(1)
    ax.axis("off")
    draw_fractal(ax)

    ax
    return ax, draw_fractal, fig


@app.cell
def _():
    import matplotlib.pyplot as plt
    return (plt,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
