# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "ell-ai==0.0.12",
#     "marimo",
#     "openai==1.50.1",
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
        # Using OpenAI

        This example shows how to use [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat) to make a chatbot backed by OpenAI.
        """
    )
    return


@app.cell
def __(mo):
    import os

    os_key = os.environ.get("OPENAI_API_KEY")
    input_key = mo.ui.text(label="OpenAI API key", kind="password")
    input_key if not os_key else None
    return input_key, os, os_key


@app.cell
def __(input_key, mo, os_key):
    # Initialize a client
    openai_key = os_key or input_key.value

    mo.stop(
        not openai_key,
        mo.md("Please set the OPENAI_API_KEY environment variable or provide it in the input field"),
    )

    mo.ui.chat(
       mo.ai.llm.openai(
            "gpt-4o",
            system_message="You are a helpful assistant.",
            api_key=openai_key,
       ),
        prompts=[
            "Hello",
            "How are you?",
            "I'm doing great, how about you?",
        ],
    )
    return (openai_key,)


if __name__ == "__main__":
    app.run()
