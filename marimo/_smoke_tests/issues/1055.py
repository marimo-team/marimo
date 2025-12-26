# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import manim_slides
    return


@app.cell
def _():
    print(1)
    return


if __name__ == "__main__":
    app.run()
