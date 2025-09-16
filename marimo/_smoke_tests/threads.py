import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.function
def foo():
    print("hi")


@app.cell
def _():
    import threading
    return (threading,)


@app.cell
def _(mo, threading):
    with mo.redirect_stdout():
        threading.Thread(target=foo).start()
    return


@app.cell
def _(mo):
    with mo.redirect_stdout():
        mo.Thread(target=foo).start()
    return


if __name__ == "__main__":
    app.run()
