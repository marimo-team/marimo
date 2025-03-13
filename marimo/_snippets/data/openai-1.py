# Copyright 2025 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # OpenAI: Chatbot

        Turn any OpenAI or any OpenAI-compatible endpoint into a chatbot.
        """
    )
    return


@app.cell
def _():
    from openai import OpenAI
    return (OpenAI,)


@app.cell
def _(mo):
    api_key = mo.ui.text(label="API Key", kind="password")
    api_key
    return (api_key,)


@app.cell
def _(api_key, mo):
    chat = mo.ui.chat(
        mo.ai.llm.openai(
            "gpt-4o-mini",
            api_key=api_key.value,
            # Change this if you are using a different OpenAI-compatible endpoint.
            # base_url="https://api.openai.com/v1",
            system_message="You are a helpful assistant.",
        ),
        prompts=["Write a haiku about recursion in programming."],
    )
    chat
    return (chat,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
