import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    from time import time
    return mo, time


@app.cell
def _(mo):
    d = mo.ui.dictionary(
        {
            "run_button1": mo.ui.run_button(label="run button 1"),
            "run_button2": mo.ui.run_button(label="run button 2"),
        }
    )
    return (d,)


@app.cell
def _(d):
    d
    return


@app.cell
def _(d, time):
    d.value, time()
    return


@app.cell
def _(d, time):
    _t = time()
    for name, button in d.items():
        if button.value:
            print(f"Clicked: at {_t}", name)
    for n, b in d.items():
        print(button.value, n)
    d.value
    return


@app.cell
def _(mo):
    run_button = mo.ui.run_button(label="single run button")
    run_button
    return (run_button,)


@app.cell
def _(run_button, time):
    if run_button.value:
        print("Clicked run button at time ", time())
    return


if __name__ == "__main__":
    app.run()
