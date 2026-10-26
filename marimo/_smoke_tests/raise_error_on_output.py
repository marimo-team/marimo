# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.1"
app = marimo.App()


@app.class_definition
class Mischief:
    def _mime_(self):
        raise ValueError("error!")


@app.cell
def _():
    mischief = Mischief()
    return (mischief,)


@app.cell
def _(mischief: Mischief):
    mischief
    return


if __name__ == "__main__":
    app.run()
