# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "groq==0.11.0",
# ]
# ///

import marimo

__generated_with = "0.9.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        # Using Groq

        This example shows how to use [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat) to make a chatbot backed by [Groq](https://groq.com/).
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    # Hyperlinking the groq as it is mentioned here - https://console.groq.com/docs/badge
    mo.md(
        r"""
        <a href="https://groq.com" target="_blank" rel="noopener noreferrer">
          <img
            src="https://groq.com/wp-content/uploads/2024/03/PBG-mark1-color.svg"
            alt="Powered by Groq for fast inference."
            width="80" height="800"
          />
        </a>
        """
    ).right()
    return


@app.cell
def __(mo):
    import os

    os_key = os.environ.get("GROQ_AI_API_KEY")
    input_key = mo.ui.text(label="Groq AI API key", kind="password")
    input_key if not os_key else None
    return input_key, os, os_key


@app.cell
def __(input_key, mo, os_key):
    key = os_key or input_key.value

    mo.stop(
        not key,
        mo.md("Please provide your Groq AI API key in the input field."),
    )
    return (key,)


@app.cell
def __(key, mo):
    chatbot = mo.ui.chat(
       mo.ai.llm.groq(
           model="llama-3.1-70b-versatile",
           system_message="You are a helpful assistant.",
           api_key=key,
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
def __(mo):
    mo.md("""Access the chatbot's historical messages with [`chatbot.value`](https://docs.marimo.io/api/inputs/chat.html#accessing-chat-history).""")
    return


@app.cell
def __(chatbot):
    # chatbot.value is the list of chat messages
    chatbot.value
    return


if __name__ == "__main__":
    app.run()
