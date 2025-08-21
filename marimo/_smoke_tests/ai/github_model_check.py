# /// script
# dependencies = [
#     "marimo",
#     "openai==1.99.9",
# ]
# [tool.marimo.runtime]
# auto_instantiate = false
# ///

import marimo

__generated_with = "0.14.16"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import openai
    import os
    return mo, openai


@app.cell
def _(mo):
    # Set up OpenAI API key
    api_key = mo.ui.text(
        value="", label="GitHub API Key. Use `gh auth token`", full_width=True
    )
    api_key
    return (api_key,)


@app.cell
def _(api_key, openai):
    client = openai.Client(
        base_url="https://api.githubcopilot.com/",
        api_key=api_key.value,
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
    if run_button.value:
        for model in ids:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=100,
                )
                print("✅ Model " + model + " passed: ")
                print(response.choices[0].message.content)
            except:
                print("❌ Model " + model + " failed")
    return


if __name__ == "__main__":
    app.run()
