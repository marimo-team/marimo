import marimo

__generated_with = "0.15.5"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    keys_1 = [f"123_{x}" for x in range(20)]
    keys_2 = [f"abc_{x}" for x in range(20)]
    return keys_1, keys_2


@app.cell
def _(mo):
    # Toggling this switch should change the keys in the tables and the initial value in the text inputs
    switch = mo.ui.switch()
    switch
    return (switch,)


@app.cell
def button(keys_1, keys_2, switch):
    keys = keys_1 if switch.value else keys_2
    return (keys,)


@app.cell
def display(keys, mo):
    table = mo.ui.table({str(k): mo.ui.text(value=k) for k in keys})
    table
    return


if __name__ == "__main__":
    app.run()
