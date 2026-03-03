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
    import asyncio

    return asyncio, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Custom streaming chatbot

    This example shows how to make a chatbot that streams responses.
    Create an async generator function that yields intermediate results,
    and watch the response appear incrementally!
    """)
    return


@app.cell
def _(asyncio, mo):
    async def streaming_echo_model(messages, config):
        """This chatbot echoes what the user says, word by word.

        Yields individual delta chunks that are accumulated by marimo.
        This follows the standard streaming pattern used by OpenAI, Anthropic,
        and other AI providers.
        """
        # Get the user's message
        user_message = messages[-1].content

        # Stream the response word by word
        response = f"You said: '{user_message}'. Here's my response streaming word by word!"
        words = response.split()

        for word in words:
            yield word + " "  # Yield delta chunks
            await asyncio.sleep(0.2)  # Delay to make streaming visible

    chatbot = mo.ui.chat(
        streaming_echo_model,
        prompts=["Hello", "Tell me a story", "What is streaming?"],
        show_configuration_controls=True
    )
    return (chatbot,)


@app.cell
def _(chatbot):
    chatbot
    return


@app.cell
def _(mo):
    mo.md("""
    ## How it works

    The key is to make your model function an **async generator** that yields **delta chunks**:

    ```python
    async def my_model(messages, config):
        # Yield individual pieces of content (deltas)
        for word in ['Building', 'up', 'text...']:
            yield word + ' '  # Each yield is a delta
            await asyncio.sleep(0.1)
    ```

    Each `yield` sends a new chunk to marimo, which accumulates and displays them.
    This follows the standard streaming pattern used by OpenAI, Anthropic, and other AI providers.

    **Important**: Yield delta chunks (new content only), not accumulated text.
    """)
    return


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
