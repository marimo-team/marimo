# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "marimo",
#     "polars>=1",
#     "pyarrow>=17",
#     "rpy2>=3.6",
#     "rpy2-arrow==0.1.3",
# ]
#
# [tool.pixi.workspace]
# channels = ["conda-forge"]
#
# [tool.pixi.dependencies]
# r-base = "*"
# r-dplyr = "*"
# r-arrow = ">=17"
# ///

import marimo

__generated_with = "0.24.2"
app = marimo.App()

with app.setup:
    import os

    # Load R from the Pixi environment at runtime.
    os.environ["RPY2_CFFI_MODE"] = "ABI"

    import marimo as mo
    import polars as pl
    import rpy2.robjects
    import rpy2_arrow.arrow


@app.cell(hide_code=True)
def _():
    mo.md("""
    # Using R

    With Pixi sandboxing, a marimo notebook can describe more than its Python
    dependencies, including system libraries and even another language's runtime.

    This demo declares R and Python dependencies together, uses marimo's
    reactivity to run R code when a slider changes, and shares the resulting
    Arrow table back to Python without copying its data.

    With [Pixi installed](https://pixi.prefix.dev/latest/installation/), open
    this notebook in a Pixi sandbox to install both its R and Python dependencies:

    ```bash
    marimo edit --sandbox=pixi examples/misc/using_r.py
    ```
    """)
    return


@app.cell
def _():
    min_len = mo.ui.slider(
        start=4.0,
        stop=8.0,
        step=0.1,
        value=5.0,
        label="Minimum sepal length (cm)",
    )
    min_len
    return (min_len,)


@app.cell
def _(min_len):
    r_table = rpy2.robjects.r(f"""
    iris |>
      dplyr::filter(Sepal.Length >= {min_len.value}) |>
      dplyr::mutate(Species = as.character(Species)) |>
      arrow::arrow_table()
    """)

    df = pl.from_arrow(rpy2_arrow.arrow.rarrow_to_py_table(r_table))
    df
    return (df,)


if __name__ == "__main__":
    app.run()
