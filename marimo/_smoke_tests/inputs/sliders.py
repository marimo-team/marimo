import marimo

__generated_with = "0.11.26"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    # Precision should be accurate, no rounding
    mo.ui.slider(
        label="1/1000 precision value",
        start=0,
        stop=0.1,
        step=0.001,
        value=0.025,
        show_value=True,
    )
    return


@app.cell
def _(mo):
    # Precision should be accurate, no rounding
    mo.ui.slider(
        label="1/1000 precision value",
        start=0,
        stop=0.0001,
        step=0.000001,
        value=0.000025,
        show_value=True,
    )
    return


if __name__ == "__main__":
    app.run()
