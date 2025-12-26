# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    def percentile(xs, p):
        "Something with a bug"
        xs = sorted(xs)
        idx = round(p / 100 * len(xs))  # here there be bugs
        return xs[idx]
    # percentile([1, 2, 3], 100)
    return


@app.cell
def _():
    import pdb
    pdb.set_trace()
    return


if __name__ == "__main__":
    app.run()
