import marimo

__generated_with = "0.9.10"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __():
    def foo():
        print("hi")
    return (foo,)


@app.cell
def __():
    import threading
    return (threading,)


@app.cell
def __(foo, mo, threading):
    with mo.redirect_stdout():
        threading.Thread(target=foo).start()
    return


@app.cell
def __(foo, mo):
    with mo.redirect_stdout():
        mo.Thread(target=foo).start()
    return


if __name__ == "__main__":
    app.run()
