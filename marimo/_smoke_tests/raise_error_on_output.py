# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __():
    class Mischief:
        def _mime_(self):
            raise ValueError("error!")
    return Mischief,


@app.cell
def __(Mischief):
    mischief = Mischief()
    return mischief,


@app.cell
def __(mischief):
    mischief
    return


if __name__ == "__main__":
    app.run()
