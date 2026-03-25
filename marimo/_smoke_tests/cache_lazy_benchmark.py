import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import os
    import time

    import numpy as np

    # Warm up numpy random so neither benchmark pays init cost
    np.random.rand(1)

    # Default small for CI smoke tests; override for real benchmarks:
    #   MARIMO_BENCH_ARRAY_SIZE=125000000 python cache_lazy_benchmark.py
    ARRAY_SIZE = int(os.environ.get("MARIMO_BENCH_ARRAY_SIZE", "100000"))
    return ARRAY_SIZE, np, time


@app.cell
def _(ARRAY_SIZE, mo, np, time):
    _start = time.perf_counter()
    with mo.persistent_cache(name="bench_pickle", method="pickle"):
        pickle_a = np.random.rand(ARRAY_SIZE)
        pickle_b = np.random.rand(ARRAY_SIZE)
        pickle_c = np.random.rand(ARRAY_SIZE)
        pickle_d = np.random.rand(ARRAY_SIZE)
        pickle_e = np.random.rand(ARRAY_SIZE)
    pickle_time = time.perf_counter() - _start

    print(f"PickleLoader (5 x {ARRAY_SIZE} numpy): {pickle_time * 1000:.1f}ms")
    return (pickle_time,)


@app.cell
def _(ARRAY_SIZE, mo, np, time):
    _start = time.perf_counter()
    with mo.persistent_cache(name="bench_lazy", method="lazy"):
        lazy_a = np.random.rand(ARRAY_SIZE)
        lazy_b = np.random.rand(ARRAY_SIZE)
        lazy_c = np.random.rand(ARRAY_SIZE)
        lazy_d = np.random.rand(ARRAY_SIZE)
        lazy_e = np.random.rand(ARRAY_SIZE)
    lazy_time = time.perf_counter() - _start

    print(f"LazyLoader (5 x {ARRAY_SIZE} numpy): {lazy_time * 1000:.1f}ms")
    return (lazy_time,)


@app.cell
def _(ARRAY_SIZE, lazy_time, pickle_time):
    print(f"\nArray size: {ARRAY_SIZE} ({ARRAY_SIZE * 8 / 1e6:.1f}MB each)")
    print(f"Pickle: {pickle_time * 1000:.1f}ms | Lazy: {lazy_time * 1000:.1f}ms")
    return


if __name__ == "__main__":
    app.run()
