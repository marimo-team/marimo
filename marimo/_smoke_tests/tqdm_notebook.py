# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.13"
app = marimo.App(width="medium")


@app.cell
def __():
    from tqdm.notebook import tqdm

    import time
    return time, tqdm


@app.cell
def __(time, tqdm):
    for i in tqdm(range(10)):
        time.sleep(0.1)
    return i,


if __name__ == "__main__":
    app.run()
