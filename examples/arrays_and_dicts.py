import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Arrays and Dictionaries")
    return


@app.cell
def __(mo):
    mo.md(
        """
        Use `mo.ui.array` and `mo.ui.dictionary` to create UI elements that wrap 
        other elements.

        Because UI elements must be assigned to global variables, 
        these functions are required when the set of elements to create is not
        known unitl runtime.
        """
    )
    return


@app.cell
def __(mo):
    create = mo.ui.button(label="Create new collections")
    return create,


@app.cell
def __(create):
    create.center()
    return


@app.cell
def __(mo):
    mo.md("UI Elements ...")
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
    mo.md(" ... and their values")
    return


@app.cell
def __(array, dictionary, mo):
    mo.hstack([array.value, dictionary.value], justify="space-around")
    return


@app.cell
def __():
    import marimo as mo
    import random
    return mo, random


if __name__ == "__main__":
    app.run()
