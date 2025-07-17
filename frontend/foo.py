import marimo

__generated_with = "0.14.11"
app = marimo.App(width="medium")


@app.cell
def _():



    return


@app.cell
def _():
    return


@app.cell
def _():
    import time
    return (time,)


@app.cell
def _(time):
    time.sleep(3)
    a = 10
    return (a,)


@app.cell
def _(a):
    a
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
