# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
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
    mo.md("""
    # Custom chatbot

    This example shows how to make a custom chatbot: just supply a function that takes two arguments,
    `messages` and `config`, and returns the chatbot's response. This response can be any object; it
    doesn't have to be a string!
    """)
    return


@app.cell
def _(mo):
    def simple_echo_model(messages, config):
        """This chatbot echoes what the user says."""
        # messages is a list of chatbot messages
        message = messages[-1]
        # Each message has two fields:
        #   message.role, which may be "user", "assistant", or "system"
        #   message.content: the content of the message
        return f"You said: {messages[-1].content}!"

    chatbot = mo.ui.chat(
        simple_echo_model,
        prompts=["Hello", "How are you?"],
        show_configuration_controls=False
    )
    chatbot
    return (chatbot,)


@app.cell
def _(mo):
    mo.md("""
    Access the chatbot's historical messages with `chatbot.value`.
    """)
    return


@app.cell
def _(chatbot):
    # chatbot.value is the list of chat messages
    chatbot.value
    return


if __name__ == "__main__":
    app.run()
