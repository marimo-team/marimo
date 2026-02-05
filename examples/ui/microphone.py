import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    microphone = mo.ui.microphone(label="Drop a beat!")
    microphone
    return (microphone,)


@app.cell
def _(microphone, mo):
    mo.stop(not microphone.value.getvalue(), "Record something with the microphone! 👆")

    mo.audio(microphone.value)
    return


if __name__ == "__main__":
    app.run()
