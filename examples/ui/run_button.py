import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    first_button = mo.ui.run_button(label="Option 1")
    second_button = mo.ui.run_button(label="Option 2")
    first_button, second_button
    return first_button, second_button


@app.cell
def _(first_button, second_button):
    if first_button.value:
        print("You chose option 1!")
    elif second_button.value:
        print("You chose option 2!")
    else:
        print("Click a button!")
    return


if __name__ == "__main__":
    app.run()
