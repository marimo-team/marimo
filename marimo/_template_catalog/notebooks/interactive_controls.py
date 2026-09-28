# Copyright 2026 Marimo. All rights reserved.
import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    stars = mo.ui.slider(
        start=1,
        stop=10,
        value=4,
        label="Number of stars",
    )
    stars
    return (stars,)


@app.cell
def _(mo, stars):
    mo.md(f"""
    # Your interactive notebook

    {"⭐" * stars.value}

    Move the slider. marimo updates this output automatically.
    """)
    return


if __name__ == "__main__":
    app.run()
