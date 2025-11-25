# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "openai==2.8.1",
# ]
# ///

import marimo

__generated_with = "0.17.8"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # OpenAI streaming chatbot

    This example shows how to use OpenAI's API with streaming responses.
    The built-in `mo.ai.llm.openai()` model automatically streams tokens
    as they arrive from the API!

    Enter your API key below to try it out.
    """)
    return


@app.cell
def _(mo):
    api_key_input = mo.ui.text(
        placeholder="sk-...",
        label="OpenAI API Key",
        kind="password",
    )
    api_key_input
    return (api_key_input,)


@app.cell
def _(api_key_input, mo):
    if api_key_input.value:
        chatbot = mo.ui.chat(
            mo.ai.llm.openai(
                "gpt-4o-mini",
                system_message="You are a helpful assistant. Keep responses concise and friendly.",
                api_key=api_key_input.value,
            ),
            prompts=[
                "Tell me a short joke",
                "What is Python?",
                "Explain streaming in one sentence",
            ],
            show_configuration_controls=True,
        )
    else:
        chatbot = mo.md("*Enter your OpenAI API key above to start chatting*")
    return (chatbot,)


@app.cell
def _(chatbot):
    chatbot
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## How it works

    The built-in OpenAI model returns an async generator that yields tokens
    as they stream from the API:

    ```python
    mo.ui.chat(
        mo.ai.llm.openai(
            "gpt-4o-mini",
            api_key="your-key",
        )
    )
    ```

    Other built-in models (`anthropic`, `google`, `groq`) work the same way.
    """)
    return


@app.cell
def _(chatbot, mo):
    # Show chat history
    mo.md(f"**Chat history:** {len(chatbot.value)} messages") if hasattr(chatbot, "value") else None
    return


@app.cell
def _(chatbot):
    # Display full history
    chatbot.value if hasattr(chatbot, "value") else None
    return


if __name__ == "__main__":
    app.run()
