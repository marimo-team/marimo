# /// script
# dependencies = [
#     "marimo",
#     "openai==1.99.9",
# ]
# [tool.marimo.runtime]
# auto_instantiate = false
# ///

import marimo

__generated_with = "0.18.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import openai
    import os
    import httpx
    return httpx, mo, openai


@app.cell
def _(mo):
    # Set up OpenAI API key
    api_key = mo.ui.text(
        value="", label="GitHub API Key. Use `gh auth token`", full_width=True
    )
    api_key
    return (api_key,)


@app.cell
def _(mo):
    with_headers = mo.ui.checkbox(label="With Headers")
    with_headers
    return (with_headers,)


@app.cell
def _(api_key, httpx, openai, with_headers):
    client = openai.Client(
        base_url="https://api.githubcopilot.com/",
        api_key=api_key.value,
        http_client=httpx.Client(verify=False),
        default_headers={
            "editor-version": "vscode/1.95.0",
            "Copilot-Integration-Id": "vscode-chat",
        }
        if with_headers.value
        else {},
    )
    models = client.models.list().model_dump()
    return client, models


@app.cell
def _(models):
    ids = [item["id"] for item in models["data"]]
    ids
    return (ids,)


@app.cell
def _(mo):
    # Button to trigger API call
    run_button = mo.ui.run_button(label="Generate Response")
    run_button
    return (run_button,)


@app.cell
def _(client, ids, run_button):
    results = {}
    if run_button.value:
        for model in ids:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=100,
                )
                msg = (
                    "✅ Model "
                    + model
                    + " passed: "
                    + response.choices[0].message.content
                )
                print(msg)
                results[model] = msg
            except:
                msg = "❌ Model " + model + " failed"
                print(msg)
                results[model] = msg
    return (results,)


@app.cell
def _(mo, results):
    mo.stop(not results)
    mo.ui.table(results, selection=None)
    return


if __name__ == "__main__":
    app.run()
