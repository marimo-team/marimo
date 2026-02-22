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
    def append():
        for i in range(3):
            mo.output.append(f"{i}: Hello from {threading.get_ident()}")
            time.sleep(1)

    return (append,)


@app.cell
def _(mo, threading, time):
    def replace():
        for i in range(3):
            mo.output.replace(f"{i}: Hello from {threading.get_ident()}")
            time.sleep(1)

    return (replace,)


@app.cell
def _(mo):
    def run_threads(fn):
        _threads = [mo.Thread(target=fn) for _ in range(3)]
        for _t in _threads:
            _t.start()
        for _t in _threads:
            _t.join()

    return (run_threads,)


@app.cell
def _(append, run_threads):
    run_threads(append)
    return


@app.cell
def _(replace, run_threads):
    run_threads(replace)
    return


if __name__ == "__main__":
    app.run()
