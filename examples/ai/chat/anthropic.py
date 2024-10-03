# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.8.22"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __(mo):
    mo.md(
        r"""
        # Using Anthropic

        This example shows how to use [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat) to make a chatbot backed by Anthropic.
        """
    )
    return


@app.cell
def __(mo):
    import os

    os_key = os.environ.get("ANTHROPIC_API_KEY")
    input_key = mo.ui.text(label="Anthropic API key", kind="password")
    input_key if not os_key else None
    return input_key, os, os_key


@app.cell
def __(input_key, mo, os_key):
    # Initialize a client
    key = os_key or input_key.value

    mo.stop(
        not key,
        mo.md("Please provide your Anthropic API key in the input field."),
    )

    mo.ui.chat(
       mo.ai.llm.anthropic(
            "claude-3-5-sonnet-20240602",
            system_message="You are a helpful assistant.",
            api_key=key,
       ),
        prompts=[
            "Hello",
            "How are you?",
            "I'm doing great, how about you?",
        ],
    )
    return (key,)


if __name__ == "__main__":
    app.run()
