# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.2"
app = marimo.App()


@app.cell
def _():
    def percentile(xs, p):
        """
        Return the p-th percentile of xs.
        """
        xs = sorted(xs)
        idx = round(p / 100 * len(xs))  # here there be bugs
        return xs[idx]


    # percentile([1, 2, 3], 100)
    return


@app.cell
def _():
    # Compute triangle numbers
    triangle = 0
    triangle_count = 20
    for i in range(1, triangle_count):
        triangle += i  # T_i = sum of 1..i
        # Debug at the 10th iteration
        # as a sanity check. Should be 55.
        if i == 10:
            print("Sanity check!")
    return


if __name__ == "__main__":
    app.run()
