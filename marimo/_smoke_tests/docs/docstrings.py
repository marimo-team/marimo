# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "docstring-to-markdown==0.15",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import docstring_to_markdown
    import marimo as mo
    from marimo._utils.docs import google_docstring_to_markdown
    return docstring_to_markdown, google_docstring_to_markdown, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    This notebook compares `docstring_to_markdown` to our internal `google_docstring_to_markdown`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    elements = {
        "button": mo.ui.button,
        "checkbox": mo.ui.checkbox,
        "dropdown": mo.ui.dropdown,
        "text": mo.ui.text,
        "radio": mo.ui.radio,
        "refs": mo.refs,
        "defs": mo.defs,
        "hstack": mo.hstack,
        "vstack": mo.vstack,
    }
    element = mo.ui.dropdown(elements, value="button")
    element
    return (element,)


@app.cell(hide_code=True)
def _(element, mo):
    mo.accordion({"MD doc": mo.plain_text(element.value.__doc__)})
    return


@app.cell
def _(docstring_to_markdown, element, mo):
    mo.md(docstring_to_markdown.convert(element.value.__doc__))
    return


@app.cell
def _(element, google_docstring_to_markdown, mo):
    mo.md(google_docstring_to_markdown(element.value.__doc__))
    return


if __name__ == "__main__":
    app.run()
