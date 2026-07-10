# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "openai==1.54.1",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Using OpenAI

    This example shows how to use [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat) to make a chatbot backed by OpenAI.
    """)
    return


@app.cell
def _(mo):
    import os

    os_key = os.environ.get("OPENAI_API_KEY")
    input_key = mo.ui.text(label="OpenAI API key", kind="password")
    input_key if not os_key else None
    return input_key, os_key


@app.cell
def _(input_key, mo, os_key):
    openai_key = os_key or input_key.value

    mo.stop(
        not openai_key,
        mo.md("Please set the OPENAI_API_KEY environment variable or provide it in the input field"),
    )
    return (openai_key,)


@app.cell
def _(mo, openai_key):
    chatbot = mo.ui.chat(
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
        allow_attachments=[
            "image/png",
            "image/jpeg"
        ],
    )
    chatbot
    return (chatbot,)


@app.cell
def _(mo):
    mo.md("""
    Access the chatbot's historical messages with [`chatbot.value`](https://docs.marimo.io/api/inputs/chat.html#accessing-chat-history).
    """)
    return


@app.cell
def _(chatbot):
    # chatbot.value is the list of chat messages
    chatbot.value
    return


if __name__ == "__main__":
    app.run()
