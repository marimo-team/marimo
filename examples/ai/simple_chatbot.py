# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "ell-ai==0.0.12",
#     "marimo",
#     "openai==1.50.1",
# ]
# ///

import marimo

__generated_with = "0.8.20"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""# Simple chatbot 🤖""")
    return


@app.cell(hide_code=True)
def __(mo):
    import os

    os_key = os.environ.get("OPENAI_API_KEY")
    input_key = mo.ui.text(label="OpenAI API key", kind="password")
    input_key if not os_key else None
    return input_key, os, os_key


@app.cell(hide_code=True)
def __(input_key, mo, os_key):
    # Initialize a client
    openai_key = os_key or input_key.value

    mo.stop(
        not openai_key,
        "Please set the OPENAI_API_KEY environment variable or provide it in the input field",
    )

    import ell
    import openai

    # Create an openai client
    client = openai.Client(api_key=openai_key)
    return client, ell, openai, openai_key


@app.cell
def __(client, ell, mo):
    @ell.simple("gpt-4o-mini-2024-07-18", client=client)
    def _my_model(prompt):
        """You are an annoying little brother, whatever I say, be sassy with your response"""
        return prompt


    mo.ui.chat(
        mo.ai.models.simple(_my_model),
        prompts=[
            "Hello",
            "How are you?",
            "I'm doing great, how about you?",
        ],
    )
    return


@app.cell
def __():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
