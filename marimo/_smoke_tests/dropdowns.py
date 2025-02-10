import marimo

__generated_with = "0.11.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    # Single selection dropdown
    dropdown1 = mo.ui.dropdown(
        options=["Option 1", "Option 2", "Option 3"], value="Option 1"
    )

    # Searchable dropdown
    dropdown2 = mo.ui.dropdown(
        options=["Red", "Blue", "Green", "Yellow"],
        value="Yellow",
        searchable=True,
    )

    # Searchable dropdown, with deselect
    dropdown2b = mo.ui.dropdown(
        options=["Red", "Blue", "Green", "Yellow"],
        value="Yellow",
        searchable=True,
        allow_select_none=True,
    )

    # Dropdown with dictionary
    dropdown3 = mo.ui.dropdown(options={"A": 1, "B": 2, "C": 3}, value="A")

    # Dropdown with custom width
    dropdown4 = mo.ui.dropdown(options=["Small", "Medium", "Large"], value="Medium")

    # Dropdown with placeholder
    dropdown5 = mo.ui.dropdown(options=["Cat", "Dog", "Bird"], value=None)
    return dropdown1, dropdown2, dropdown2b, dropdown3, dropdown4, dropdown5


@app.cell
def _(dropdown1, dropdown2, dropdown2b, dropdown3, dropdown4, dropdown5):
    [
        dropdown1,
        dropdown2,
        dropdown2b,
        dropdown3,
        dropdown4,
        dropdown5,
    ]
    return


@app.cell
def _(mo):
    # Virtualized
    mo.ui.dropdown(
        options=[str(i) for i in range(1000)],
        value=None,
        searchable=True,
        allow_select_none=True,
    )
    return


if __name__ == "__main__":
    app.run()
