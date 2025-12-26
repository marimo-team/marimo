# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import polars as pl
    import numpy as np

    d = pl.DataFrame({"a": [np.array(np.arange(5) + i) for i in range(5)]})
    res = d.select(
        pl.col("a").map_batches(
            lambda x: pl.Series(
                [{"filt_value": np.dot(x, x), "filt_phase": 5.0}], strict=False
            ),
            is_elementwise=True,
        ),
    )
    return (res,)


@app.cell
def _(res):
    res
    return


if __name__ == "__main__":
    app.run()
