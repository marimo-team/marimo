import marimo

__generated_with = "0.1.82"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    x = mo.ui.dictionary(
        {
            str(i): mo.ui.button(value=i, label=str(i), on_click=lambda v: v + 1)
            for i in range(10)
        }
    )
    x
    return x,


@app.cell
def __(__get_item__):
    __get_item__
    return


@app.cell
def __(mo, x):
    mo.ui.table([{"button": btn} for btn in x.values()])
    return


@app.cell
def __(x):
    x.value
    return


if __name__ == "__main__":
    app.run()
