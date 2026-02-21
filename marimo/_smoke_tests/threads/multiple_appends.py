import marimo

__generated_with = "0.20.1"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import time
    import threading

    return mo, threading, time


@app.cell
def _(mo, threading, time):
    def target():
        for i in range(3):
            mo.output.append(f"{i}: Hello from {threading.get_ident()}")
            time.sleep(1)
        mo.output.replace("This thread is done")

    return (target,)


@app.cell
def _(mo, target):
    _threads = [mo.Thread(target=target) for _ in range(3)]
    for _t in _threads:
        _t.start()
    for _t in _threads:
        _t.join()
    return


if __name__ == "__main__":
    app.run()
