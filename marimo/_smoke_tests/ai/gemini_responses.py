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
def _(api_token):
    from google import genai

    client = genai.Client(api_key=api_token.value)
    return genai, client


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### Non-streaming""")
    return


@app.cell
def _(client, tools):
    client.models.generate_content_stream(
        model="gemini-2.5-flash-preview-05-20",
        contents="Create a function that takes a list of numbers and returns the sum of all the numbers in the list.",
        config={
            "tools": tools.value,
        }
    )
    return


if __name__ == "__main__":
    app.run()
