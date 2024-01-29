# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.85"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
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
    return append, data, dict_template, partial, x


@app.cell
def __(mo, x):
    mo.ui.table([{"data": "foo", "button": btn} for btn in x.values()])
    return


@app.cell
def __(data, x):
    # x.value counts how many times each button has been clicked
    # data is a log of button clicks
    x.value, data
    return


@app.cell
def __(dict_template, mo):
    composite = mo.ui.array(
        [
            mo.ui.slider(1, 10),
            mo.ui.array([mo.ui.checkbox(False), mo.ui.slider(10, 20)]),
            mo.ui.dictionary(dict_template),
        ]
    )
    return composite,


@app.cell
def __():
    10
    return


@app.cell
def __(composite):
    composite[0], composite[1], composite[2]
    return


@app.cell
def __(composite, mo):
    mo.accordion({"Push a button": composite[2]["0"]})
    return


@app.cell
def __(composite):
    composite.value
    return


@app.cell
def __():
    def change_printer(v):
        print("changed ", v)
    return change_printer,


@app.cell
def __(checkboxes):
    [_item for _item in checkboxes]
    return


@app.cell
def __(change_printer, mo):
    checkboxes = mo.ui.array(
        [mo.ui.checkbox(False, on_change=change_printer) for i in range(5)]
    )
    return checkboxes,


if __name__ == "__main__":
    app.run()
