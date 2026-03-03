import marimo

__generated_with = "0.19.7"
app = marimo.App(app_title="In Memory Cache")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    @mo.persistent_cache
    def sleep_for(t: int):
        import time

        print("Sleeping")
        time.sleep(t)
        return t

    return (sleep_for,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Use `mo.persistent_cache` to cache the outputs of expensive computations to persistent storage. The first
    time the function is called with unseen arguments, it will execute and
    return the computed value. Subsequent calls with the same arguments will
    return cached results.

    Experiment with the invocation below to get a feel for how this works.
    """)
    return


@app.cell
def _(sleep_for):
    sleep_for(1)
    return


if __name__ == "__main__":
    app.run()
