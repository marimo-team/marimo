import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import time

    import numpy as np

    # Warm up numpy random so neither benchmark pays init cost
    np.random.rand(1)
    return np, time


@app.cell
def _(mo, np, time):
    _start = time.perf_counter()
    with mo.persistent_cache(name="bench_pickle", method="pickle"):
        pickle_a = np.random.rand(125_000_000)
        pickle_b = np.random.rand(125_000_000)
        pickle_c = np.random.rand(125_000_000)
        pickle_d = np.random.rand(125_000_000)
        pickle_e = np.random.rand(125_000_000)
    pickle_time = time.perf_counter() - _start

    print(f"PickleLoader (5 x 1GB numpy): {pickle_time * 1000:.1f}ms")
    return (pickle_time,)


@app.cell
def _(mo, np, time):
    _start = time.perf_counter()
    with mo.persistent_cache(name="bench_lazy", method="lazy"):
        lazy_a = np.random.rand(125_000_000)
        lazy_b = np.random.rand(125_000_000)
        lazy_c = np.random.rand(125_000_000)
        lazy_d = np.random.rand(125_000_000)
        lazy_e = np.random.rand(125_000_000)
    lazy_time = time.perf_counter() - _start

    print(f"LazyLoader (5 x 1GB numpy): {lazy_time * 1000:.1f}ms")
    return (lazy_time,)


@app.cell
def _(lazy_time, pickle_time):
    print(f"\nPickle: {pickle_time * 1000:.1f}ms | Lazy: {lazy_time * 1000:.1f}ms")
    return


if __name__ == "__main__":
    app.run()
