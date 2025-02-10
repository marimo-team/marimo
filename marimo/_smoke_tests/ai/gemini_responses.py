import marimo

__generated_with = "0.11.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os
    return mo, os


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Setup""")
    return


@app.cell(hide_code=True)
def _(mo, os):
    api_token = mo.ui.text(
        label="Gemini API Token", value=os.environ.get("GEMINI_API_KEY") or ""
    )
    api_token
    return (api_token,)


@app.cell(hide_code=True)
def _(api_token, mo):
    mo.callout("Missing API Key", kind="danger") if not api_token.value else None
    return


@app.cell(hide_code=True)
def _(mo):
    tools = mo.ui.multiselect(["code_execution"], value=[], label="Tools")
    tools
    return (tools,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## Run some queries""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""### Streaming""")
    return


@app.cell
def _(api_token, tools):
    import google.generativeai as genai

    genai.configure(api_key=api_token.value)
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp", tools=tools.value
    )

    model.generate_content(
        "Create a function that takes a list of numbers and returns the sum of all the numbers in the list.",
        stream=True,
    )
    return genai, model


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### Non-streaming""")
    return


@app.cell
def _(model):
    model.generate_content(
        "Create a function that takes a list of numbers and returns the sum of all the numbers in the list."
    )
    return


if __name__ == "__main__":
    app.run()
