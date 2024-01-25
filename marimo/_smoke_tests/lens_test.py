import marimo

__generated_with = "0.1.81"
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
    return append, data, partial, x


@app.cell
def __(mo, x):
    mo.ui.table([{"button": btn} for btn in x.elements.values()])
    return


@app.cell
def __(data, x):
    x.value, data
    return


@app.cell
def __(mo, x):
    composite = mo.ui.array(
        [
            mo.ui.slider(1, 10),
            mo.ui.array([mo.ui.checkbox(False), mo.ui.slider(10, 20)]),
            mo.ui.dictionary(x),
        ]
    )
    return composite,


if __name__ == "__main__":
    app.run()
