import marimo

__generated_with = "0.1.5"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md("# Character Count").left()
    return


@app.cell
def __(mo):
    text = mo.ui.text_area(placeholder="Enter text ...", label="Character count")
    return text,


@app.cell
def __(mo, text):
    mo.hstack(
        [text, mo.md(f"`{len(text.value)} characters`")],
        justify="start",
        align="end",
        gap=1,
    )
    return


if __name__ == "__main__":
    app.run()
