# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.9.14"
app = marimo.App()


@app.cell(hide_code=True)
def __(mo):
    mo.md("""# Arrays and Dictionaries""")
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        Use `mo.ui.array` and `mo.ui.dictionary` to create UI elements that wrap 
        other elements.

        Because UI elements must be assigned to global variables, 
        these functions are required when the set of elements to create is not
        known until runtime.
        """
    )
    return


@app.cell
def __(mo):
    create = mo.ui.button(label="Create new collections")
    return (create,)


@app.cell
def __(create):
    create.center()
    return


@app.cell
def __(mo):
    mo.md("""UI Elements ...""")
    return


@app.cell
def __(create, mo, random):
    create

    array = mo.ui.array(
        [mo.ui.text()]
        + [mo.ui.slider(1, 10) for _ in range(0, random.randint(2, 5))],
    )
    dictionary = mo.ui.dictionary(
        {str(i): mo.ui.slider(1, 10) for i in range(0, random.randint(2, 5))}
    )

    mo.hstack([array, dictionary], justify="space-around")
    return array, dictionary


@app.cell
def __(mo):
    mo.md("""... and their values""")
    return


@app.cell
def __(array, dictionary, mo):
    mo.hstack([array.value, dictionary.value], justify="space-around")
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        Key difference between marimo dict and standard python dict:

        The main reason to use `mo.ui.dictionary` is for reactive execution — when you interact with an element in a `mo.ui.dictionary`, all cells that reference the `mo.ui.dictionary` run automatically, just like all other ui elements. When you use a regular dictionary, you don't get this reactivity.
        """
    )
    return


@app.cell(hide_code=True)
def __(create, mo):
    create

    slider = mo.ui.slider(1, 10, show_value=True)
    text = mo.ui.text()
    date = mo.ui.date()

    mo_d = mo.ui.dictionary(
        {
            "slider": slider,
            "text": text,
            "date": date,
        }
    )

    py_d = {
        "slider": slider,
        "text": text,
        "date": date,
    }

    mo.hstack(
        [
            mo.vstack(["marimo dict", mo_d]),
            mo.vstack(["original elements", mo.vstack([slider, text, date])]),
            mo.vstack(["python dict", py_d]),
        ],
        justify="space-around",
    )
    return date, mo_d, py_d, slider, text


@app.cell(hide_code=True)
def __(mo, mo_d, py_d):
    mo_d_ref = {k: mo_d[k].value for k in mo_d.value.keys()}
    py_d_ref = {k: py_d[k].value for k in py_d.keys()}
    mo.hstack(
        [
            mo.vstack(["reference of marimo dict", mo_d_ref]),
            mo.vstack(["reference of python dict", py_d_ref]),
        ],
        justify="space-around",
    )
    return mo_d_ref, py_d_ref


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""Notice that when you interact with the UI elements in the marimo dict, the reference of marimo dict updates automatically. However, when you interact with the elements in the python dict, you need to manually re-run the cell to see the updated values.""")
    return


@app.cell
def __():
    import marimo as mo
    import random
    return mo, random


if __name__ == "__main__":
    app.run()
