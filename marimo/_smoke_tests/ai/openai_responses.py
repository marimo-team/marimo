import marimo

__generated_with = "0.11.2"
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
        label="OpenAI API Token", value=os.environ.get("OPENAI_API_KEY") or ""
    )
    api_token
    return (api_token,)


@app.cell(hide_code=True)
def _(api_token, mo):
    (mo.callout("Missing API Key", kind="danger") if not api_token.value else None)
    return


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
    from openai import OpenAI

    client = OpenAI(api_key=api_token.value)
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {
                "role": "user",
                "content": "Create a function that takes a list of numbers and returns the sum of all the numbers in the list.",
            }
        ],
        stream=True,
    )
    response
    return OpenAI, client, response


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### Non-streaming""")
    return


@app.cell
def _(client):
    client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {
                "role": "user",
                "content": "Create a function that takes a list of numbers and returns the sum of all the numbers in the list.",
            }
        ],
    )
    return


if __name__ == "__main__":
    app.run()
