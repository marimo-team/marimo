# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "dagger-io==0.14.0",
#     "ell-ai==0.0.14",
#     "marimo",
#     "openai==1.55.0",
#     "pydantic==2.8.2",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import ell
    import textwrap

    return ell, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Chatbot code-interpreter with [Dagger](https://dagger.io/)

    This example shows how to create a code-interpreter that executes code using [Dagger](https://dagger.io/) so the code is run in an isolated container.

    This example requires Docker running on your computer.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    backend = mo.ui.dropdown(["ollama", "openai"], label="Backend", value="openai")
    backend
    return (backend,)


@app.cell(hide_code=True)
def _(mo):
    # OpenAI config
    import os
    import openai

    input_key = mo.ui.text(
        label="OpenAI API key",
        kind="password",
        value=os.environ.get("OPENAI_API_KEY", ""),
    )
    input_key
    return (input_key,)


@app.cell(hide_code=True)
def _(backend, input_key, mo):
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
def _():
    import dagger

    return (dagger,)


@app.cell
def _(mo):
    files = mo.ui.file(kind="area")
    files
    return (files,)


@app.cell
def _(mo):
    packages = mo.ui.text_area(label="Packages", value="pandas")
    packages
    return (packages,)


@app.cell
def _(files):
    [file.name for file in files.value]
    return


@app.cell
def _(dagger, ell, files, mo, packages):
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
                .with_new_file("/app/requirements.txt", contents=packages.value)
                .with_exec(["pip", "install", "-r", "/app/requirements.txt"])
            )

            for file in files.value:
                container = container.with_new_file(
                    f"/app/{file.name}", contents=file.contents.decode("utf-8")
                )

            result = (
                await container.with_workdir("/app")
                .with_exec(["python", "/app/script.py"])
                .stdout()
            )

        return mo.vstack(
            [
                mo.ui.code_editor(code, language="python", disabled=True),
                mo.md(result),
            ]
        )

    return (execute_code,)


@app.function(hide_code=True)
def describe_file(file):
    if file.name.endswith(".py"):
        return f"Python file: {file.name}"
    if file.name.endswith(".txt"):
        return f"Text file: {file.name}"
    if file.name.endswith(".csv"):
        return f"CSV file: {file.name}. Headers: {file.contents.decode('utf-8').splitlines()[0]}"
    return f"File: {file.name}"


@app.cell
def _(client, ell, execute_code, files, mo, model, packages):
    files_instructions = ""
    packages_instructions = ""
    if files.value:
        files_instructions = f"""
        Here are the files you can access:"

        {"\n".join([describe_file(file) for file in files.value])}
        """

    if packages.value:
        packages_instructions = f"""
        Here are the python packages you can access:"
        {packages.value}
        """


    @ell.complex(
        model=model,
        tools=[execute_code],
        client=client,
    )
    def custom_chatbot(messages, config) -> str:
        system_message = ell.system(f"""
            You are data scientist with access to writing python code.

            {files_instructions}

            {packages_instructions}
            """)
        return [system_message] + [
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

    return (my_model,)


@app.cell
def _(mo, my_model):
    mo.ui.chat(
        my_model,
        prompts=[
            "What is the square root of {{number}}?",
            f"Can you sum this list using python: {list(range(1, 10))}",
        ],
    )
    return


if __name__ == "__main__":
    app.run()
