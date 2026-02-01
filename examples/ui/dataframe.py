# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "vega-datasets==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from vega_datasets import data

    return (data,)


@app.cell(hide_code=True)
def _(mo):
    lazy_button = mo.ui.checkbox(label="Lazy Dataframe")
    lazy_button
    return (lazy_button,)


@app.cell
def _(data, lazy_button, mo):
    def format_length(value: float) -> str:
        return f"{value:.1f} cm"

    dataframe_transformer = mo.ui.dataframe(
        data.iris(),
        lazy=lazy_button.value,
        format_mapping={
            "sepal_length": format_length,
            "sepal_width": "{:.1f}".format,
        },
    )
    dataframe_transformer
    return (dataframe_transformer,)


@app.cell
def _(dataframe_transformer):
    dataframe_transformer.value
    return


if __name__ == "__main__":
    app.run()
