import marimo

__generated_with = "0.10.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    initial_code = """# implement foo below
    def foo():
        ...
    """

    editor = mo.ui.code_editor(
        value=initial_code,
        language="python"
    )
    editor
    return editor, initial_code


@app.cell
def _(editor):
    editor.value
    return


if __name__ == "__main__":
    app.run()
