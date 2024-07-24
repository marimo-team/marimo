# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.9"
app = marimo.App(width="medium")


@app.cell
def __():
    raise ValueError("".join([str(i) for i in range(1000)]))
    return


if __name__ == "__main__":
    app.run()
