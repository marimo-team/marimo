import marimo

__generated_with = "0.8.13"
app = marimo.App(width="columns")


@app.cell
def __():
    import marimo as mo
    from vega_datasets import data
    return data, mo


@app.cell
def __(mo):
    mo.ui.button(
        kind="success",
        label="You may click.",
        on_click=lambda scold: print("Very good!")
    )
    return


@app.cell
def __(mo):
    mo.ui.button(
        kind="danger",
        label="You may not click!",
        on_click=lambda scold: print("Hey! Stop it!")
    )
    return


@app.cell
def __(data):
    df = data.iris()
    df
    return df,


@app.cell
def __(data):
    data.airports()
    return


@app.cell
def __():
    return


if __name__ == "__main__":
    app.run()
