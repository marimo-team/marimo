# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    from functools import partial

    data = []


    def append(v, i):
        del v
        data.append(i)


    dict_template = {
        str(i): mo.ui.button(
            value=i,
            label=str(i),
            on_click=lambda v: v + 1,
            on_change=partial(append, i=i),
        )
        for i in range(3)
    }


    x = mo.ui.dictionary(
        {
            str(i): mo.ui.button(
                value=i,
                label=str(i),
                on_click=lambda v: v + 1,
                on_change=partial(append, i=i),
            )
            for i in range(3)
        }
    )
    # x
    return data, dict_template, x


@app.cell
def _(mo, x):
    mo.ui.table([{"data": "foo", "button": btn} for btn in x.values()])
    return


@app.cell
def _(data, x):
    # x.value counts how many times each button has been clicked
    # data is a log of button clicks
    x.value, data
    return


@app.cell
def _(dict_template, mo):
    composite = mo.ui.array(
        [
            mo.ui.slider(1, 10),
            mo.ui.array([mo.ui.checkbox(False), mo.ui.slider(10, 20)]),
            mo.ui.dictionary(dict_template),
        ]
    )
    return (composite,)


@app.cell
def _():
    10
    return


@app.cell
def _(composite):
    composite[0], composite[1], composite[2]
    return


@app.cell
def _(composite, mo):
    mo.accordion({"Push a button": composite[2]["0"]})
    return


@app.cell
def _(composite):
    composite.value
    return


@app.function
def change_printer(v):
    print("changed ", v)


@app.cell
def _(checkboxes):
    [_item for _item in checkboxes]
    return


@app.cell
def _(mo):
    checkboxes = mo.ui.array(
        [mo.ui.checkbox(False, on_change=change_printer) for i in range(5)]
    )
    return (checkboxes,)


if __name__ == "__main__":
    app.run()
