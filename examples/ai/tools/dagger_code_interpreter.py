# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "dagger-io==0.13.5",
#     "ell-ai==0.0.13",
#     "marimo",
#     "openai==1.51.0",
# ]
# ///

import marimo

__generated_with = "0.9.7"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def __():
    import marimo as mo
    import ell
    import textwrap
    return ell, mo, textwrap


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        # Chatbot code-interpreter with [Dagger](https://dagger.io/)

        This example shows how to create a code-interpreter that executes code using [Dagger](https://dagger.io/) so the code is run in an isolated container.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    backend = mo.ui.dropdown(["ollama", "openai"], label="Backend", value="openai")
    backend
    return (backend,)


@app.cell(hide_code=True)
def __(mo):
    # OpenAI config
    import os
    import openai

    input_key = mo.ui.text(
        label="OpenAI API key",
        kind="password",
        value=os.environ.get("OPENAI_API_KEY", ""),
    )
    input_key
    return input_key, openai, os


@app.cell(hide_code=True)
def __(backend, input_key, mo):
    def _get_open_ai_client():
        openai_key = input_key.value

        import openai

        mo.stop(
            not openai_key,
            mo.md(
                "Please set the `OPENAI_API_KEY` environment variable or provide it in the input field"
            ),
        )

        return openai.Client(api_key=openai_key)


    def _get_ollama_client():
        import openai

        return openai.Client(
            api_key="ollama",
            base_url="http://localhost:11434/v1",
        )


    client = (
        _get_ollama_client()
        if backend.value == "ollama"
        else _get_open_ai_client()
    )
    model = "llama3.1" if backend.value == "ollama" else "gpt-4-turbo"
    return client, model


@app.cell
def __():
    import dagger
    return (dagger,)


@app.cell
def __(dagger, ell, mo):
    def code_fence(code):
        return f"```python\n\n{code}\n\n```"


    @ell.tool()
    async def execute_code(code: str):
        """
        Execute python using Dagger. You MUST have print() in the last expression.
        """
        async with dagger.Connection() as _dag:
            container = (
                _dag.container()
                .from_("python:3.12-slim")
                .with_new_file("/app/script.py", contents=code)
            )

            result = await container.with_exec(
                ["python", "/app/script.py"]
            ).stdout()

        results = [
            "**Work**",
            code_fence(code),
            "**Result**",
            code_fence(result),
        ]
        return mo.md("\n\n".join(results))
    return code_fence, execute_code


@app.cell
def __(client, ell, execute_code, mo, model):
    @ell.complex(model=model, tools=[execute_code], client=client)
    def custom_chatbot(messages, config) -> str:
        """You are data scientist with access to writing python code."""
        return [
            ell.user(message.content)
            if message.role == "user"
            else ell.assistant(message.content)
            for message in messages
        ]


    def my_model(messages, config):
        response = custom_chatbot(messages, config)
        if response.tool_calls:
            return response.tool_calls[0]()
        return mo.md(response.text)
    return custom_chatbot, my_model


@app.cell
def __(mo, my_model):
    numbers = [x for x in range(1, 10)]

    mo.ui.chat(
        my_model,
        prompts=[
            "What is the square root of {{number}}?",
            f"Can you sum this list using python: {numbers}",
        ],
    )
    return (numbers,)


if __name__ == "__main__":
    app.run()
