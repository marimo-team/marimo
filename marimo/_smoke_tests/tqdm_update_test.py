# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    from tqdm.notebook import tqdm, trange
    import time
    return time, tqdm, trange


@app.cell
def _(time, tqdm):
    # Test regular iteration
    for i in tqdm(range(5)):
        time.sleep(0.1)
    return


@app.cell
def _(time, trange):
    # Test regular iteration
    for i in trange(5):
        time.sleep(0.1)
    return


@app.cell
def _(time, tqdm):
    # Test manual update method
    pbar = tqdm(total=5)
    for i in range(5):
        time.sleep(0.1)
        pbar.update(1)  # Explicitly calling update
    pbar.close()
    return


@app.cell
def _(time, tqdm):
    # Test update with different increment
    pbar = tqdm(total=50)
    for i in range(0, 50, 5):
        time.sleep(0.1)
        pbar.update(5)  # Update by 5 each time
    pbar.close()
    return


if __name__ == "__main__":
    app.run()
