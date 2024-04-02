# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.2.8"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import random
    return mo, random


@app.cell
def __(mo):
    reset_button = mo.ui.button(label="Reset")
    reset_button
    return reset_button,


@app.cell
def __(mo, random, reset_button):
    reset_button
    my_pick = random.randint(0, 10)
    mo.accordion({"My pick": my_pick})
    return my_pick,


@app.cell
def __(mo):
    refresh = mo.ui.refresh(options=["1s", "10s", "1m", "100ms"])
    mo.md(f"Choose an interval to guess {refresh}")
    return refresh,


@app.cell
def __(mo, my_pick, random, refresh):
    refresh
    guess = random.randint(0, 10)
    mo.stop(
        guess == my_pick,
        mo.md(f"That is correct: {my_pick}").callout(kind="success"),
    )

    mo.md(f"Not correct, your guess was {random.randint(0, 10)}").callout(
        kind="warn"
    )
    return guess,


if __name__ == "__main__":
    app.run()
