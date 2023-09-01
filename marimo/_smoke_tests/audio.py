# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.4"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mic = mo.ui.microphone(label="What is your name?")
    mic
    return mic,


@app.cell
def __(mic, mo):
    mo.audio(mic.value)
    return


@app.cell
def __(mo):
    mo.audio(src="https://samplelib.com/lib/preview/mp3/sample-3s.mp3")
    return


if __name__ == "__main__":
    app.run()
