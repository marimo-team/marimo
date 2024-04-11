# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.8"
app = marimo.App()


@app.cell
def __():
    import manim_slides
    return manim_slides,


@app.cell
def __():
    print(1)
    return


if __name__ == "__main__":
    app.run()
