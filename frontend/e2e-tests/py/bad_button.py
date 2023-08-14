import marimo

__generated_with = "0.0.1"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    b = mo.ui.button(value=None, label='Bad button', on_click=lambda v: v + 1)
    b
    return b,


@app.cell
def __(b):
    b.value
    return


if __name__ == "__main__":
    app.run()
