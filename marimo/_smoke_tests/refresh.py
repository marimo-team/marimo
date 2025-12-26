# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import random
    return mo, random


@app.cell
def _(mo):
    reset_button = mo.ui.button(label="Reset")
    reset_button
    return (reset_button,)


@app.cell
def _(mo, random, reset_button):
    reset_button
    my_pick = random.randint(0, 10)
    mo.accordion({"My pick": my_pick})
    return (my_pick,)


@app.cell
def _(mo):
    refresh = mo.ui.refresh(options=["1s", "10s", "1m", "100ms"])
    mo.md(f"Choose an interval to guess {refresh}")
    return (refresh,)


@app.cell
def _(mo, my_pick, random, refresh):
    refresh
    guess = random.randint(0, 10)
    mo.stop(
        guess == my_pick,
        mo.md(f"That is correct: {my_pick}").callout(kind="success"),
    )

    mo.md(f"Not correct, your guess was {random.randint(0, 10)}").callout(
        kind="warn"
    )
    return


if __name__ == "__main__":
    app.run()
