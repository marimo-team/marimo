# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.9.0"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
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
    openai_key = os_key or input_key.value

    mo.stop(
        not openai_key,
        mo.md("Please set the OPENAI_API_KEY environment variable or provide it in the input field"),
    )
    return (openai_key,)


@app.cell
def __(mo, openai_key):
    chatbot = mo.ui.chat(
       mo.ai.llm.openai(
            "gpt-4o",
            system_message="You are a helpful assistant.",
            api_key=openai_key,
            allow_attachments=[
            "image/png",
            "image/jpeg"
        ],
       ),
        prompts=[
            "Hello",
            "How are you?",
            "I'm doing great, how about you?",
        ],
    )
    chatbot
    return (chatbot,)


@app.cell
def __(mo):
    mo.md("""Access the chatbot's historical messages with `chatbot.value`.""")
    return


@app.cell
def __(chatbot):
    # chatbot.value is the list of chat messages
    chatbot.value
    return


if __name__ == "__main__":
    app.run()
