#!/usr/bin/env -S uv run --script
#SBATCH --job-name=marimo-batch
#SBATCH --output=marimo-%j.out
#SBATCH --cpus-per-task=4
#SBATCH --mem=16GB
#SBATCH --time=00:30:00

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "numpy",
# ]
# ///

import marimo

__generated_with = "0.23.16"
app = marimo.App(app_title="Slurm batch example")

with app.setup:
    import argparse
    import time

    import marimo as mo
    import numpy as np


@app.cell(hide_code=True)
def _():
    mo.md("""
    # A notebook / Slurm job

    This file is simultaneously:

    * a marimo notebook — `marimo edit submit_notebook.py`
    * a Python script — `uv run submit_notebook.py --n 500000`
    * a Slurm job — `chmod +x submit_notebook.py && sbatch submit_notebook.py`

    The `#SBATCH` directives, the dependencies (PEP 723), and the code all
    live in this one file.
    """)
    return


@app.cell
def _():
    parser = argparse.ArgumentParser(description="Slurm batch example")
    parser.add_argument("--n", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)

    if mo.running_in_notebook():
        _args = parser.parse_args([])
    else:
        _args = parser.parse_args()
    # Unpack into plain values: the cache keys on the values a cached cell
    # reads, and primitives hash by content (a Namespace does not).
    n, seed = _args.n, _args.seed
    return n, seed


@app.cell
def _(n, seed):
    # Stand-in for real work. The cache persists to disk, so a resubmitted
    # job with the same arguments restores instead of recomputing, while
    # new values of `n` or `seed` recompute.
    with mo.persistent_cache("monte_carlo_pi"):
        _start = time.perf_counter()
        _rng = np.random.default_rng(seed)
        _points = _rng.random((n, 2))
        pi_estimate = 4.0 * float(((_points**2).sum(axis=1) <= 1.0).mean())
        elapsed = time.perf_counter() - _start
    return elapsed, pi_estimate


@app.cell
def _(elapsed, n, pi_estimate):
    print(f"pi ~= {pi_estimate:.6f} (n={n:,}, {elapsed:.2f}s)")
    return


if __name__ == "__main__":
    app.run()
