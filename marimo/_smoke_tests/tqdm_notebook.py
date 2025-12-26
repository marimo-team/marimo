# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    from tqdm.notebook import tqdm

    import time
    return time, tqdm


@app.cell
def _(time, tqdm):
    for i in tqdm(range(10)):
        time.sleep(0.1)
    return


if __name__ == "__main__":
    app.run()
