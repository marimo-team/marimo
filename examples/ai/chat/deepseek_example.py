# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "openai==1.60.2",
# ]
# ///

import marimo

__generated_with = "0.10.17"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # Using DeepSeek

        This example shows how to use [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat/?h=mo.ui.chat) to make a chatbot backed by [Deepseek](https://deepseek.com/).
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        <a href="https://api-docs.deepseek.com/" target="_blank" rel="noopener noreferrer">
          <img
            src="https://chat.deepseek.com/deepseek-chat.jpeg"
            alt="Powered by deepseek"
            width="450"
          />
        </a>
        """
    ).center()
    return


@app.cell
def _(mo):
    import os

    os_key = os.environ.get("DEEPSEEK_API_KEY")
    input_key = mo.ui.text(label="Deepseek API key", kind="password")
    input_key if not os_key else None
    return input_key, os, os_key


@app.cell
def _(input_key, mo, os_key):
    key = os_key or input_key.value

    mo.stop(
        not key,
        mo.md("Please provide your Deepseek AI API key in the input field."),
    )
    return (key,)


@app.cell
def _(key, mo):
    chatbot = mo.ui.chat(
       mo.ai.llm.openai(
           model="deepseek-reasoner",
           system_message="You are a helpful assistant.",
           api_key=key,
           base_url="https://api.deepseek.com",
       ),
        prompts=[
            "Hello",
            "How are you?",
            "I'm doing great, how about you?",
        ],
    )
    chatbot
    return (chatbot,)


@app.cell(hide_code=True)
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
