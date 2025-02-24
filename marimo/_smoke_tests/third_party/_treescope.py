# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "numpy==2.2.3",
#     "treescope==0.1.9",
# ]
# ///

import marimo

__generated_with = "0.11.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import treescope
    import numpy as np

    my_array = np.cos(np.arange(300).reshape((10,30)) * 0.2)
    figure = treescope.render_array(my_array)
    mo.iframe(figure._repr_html_())
    return figure, mo, my_array, np, treescope


@app.cell
def _(figure):
    figure
    return


if __name__ == "__main__":
    app.run()
