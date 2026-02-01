import marimo

__generated_with = "0.19.7"
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

    editor = mo.ui.code_editor(value=initial_code, language="python")
    editor
    return (editor,)


@app.cell
def _(editor):
    editor.value
    return


@app.cell
def _(mo):
    copy_editor = mo.ui.code_editor(
        value="let a = 'b';",
        language="javascript",
        show_copy_button=False,
    )
    copy_editor
    return


if __name__ == "__main__":
    app.run()
