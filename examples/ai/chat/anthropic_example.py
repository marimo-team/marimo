# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "anthropic",
# ]
# ///

import marimo

__generated_with = "0.13.10"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md(
        r"""
    # Using Anthropic

    This example shows how to use [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat) to make a chatbot backed by Anthropic.
    """
    )
    return


@app.cell
def _(mo):
    import os

    os_key = os.environ.get("ANTHROPIC_API_KEY")
    input_key = mo.ui.text(label="Anthropic API key", kind="password")
    input_key if not os_key else None
    return input_key, os_key


@app.cell
def _(input_key, mo, os_key):
    key = os_key or input_key.value

    mo.stop(
        not key,
        mo.md("Please provide your Anthropic API key in the input field."),
    )
    return (key,)


@app.cell
def _(key, mo):
    chatbot = mo.ui.chat(
        mo.ai.llm.anthropic(
            "claude-3-7-sonnet-20250219",
            system_message="You are a helpful assistant.",
            api_key=key,
        ),
        allow_attachments=[
            "image/png",
            "image/jpeg",
        ],
        prompts=[
            "Hello",
            "How are you?",
            "I'm doing great, how about you?",
        ],
        max_height=400,
    )
    chatbot
    return (chatbot,)


@app.cell
def _(mo):
    mo.md("""Access the chatbot's historical messages with [`chatbot.value`](https://docs.marimo.io/api/inputs/chat.html#accessing-chat-history).""")
    return


@app.cell
def _(chatbot):
    # chatbot.value is the list of chat messages
    chatbot.value
    return


if __name__ == "__main__":
    app.run()
