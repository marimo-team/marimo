# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "ell-ai==0.0.13",
#     "marimo",
#     "openai==1.51.0",
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
    # Creating a code interpreter

    This example shows how to create a code-interpreter in a few lines of code.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    backend = mo.ui.dropdown(["ollama", "openai"], label="Backend", value="ollama")
    backend
    return (backend,)


@app.cell(hide_code=True)
def _(backend, mo):
    # OpenAI config
    import os
    import openai

    os_key = os.environ.get("OPENAI_API_KEY")
    input_key = mo.ui.text(
        label="OpenAI API key",
        kind="password",
        value=os.environ.get("OPENAI_API_KEY", ""),
    )
    input_key if backend.value == "openai" else None
    return input_key, openai, os_key


@app.cell
def _(openai):
    client = openai.Client(
        api_key="ollama",
        base_url="http://localhost:11434/v1",
    )
    return (client,)


@app.cell(hide_code=True)
def _(backend, input_key, mo, os_key):
    def _get_open_ai_client():
        openai_key = os_key or input_key.value

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


    _client = (
        _get_ollama_client()
        if backend.value == "ollama"
        else _get_open_ai_client()
    )
    model = "llama3.1" if backend.value == "ollama" else "gpt-4-turbo"
    return (model,)


@app.function(hide_code=True)
# https://stackoverflow.com/questions/33908794/get-value-of-last-expression-in-exec-call
def exec_with_result(script, globals=None, locals=None):
    """Execute a script and return the value of the last expression"""
    import ast

    stmts = list(ast.iter_child_nodes(ast.parse(script)))
    if not stmts:
        return None
    if isinstance(stmts[-1], ast.Expr):
        # the last one is an expression and we will try to return the results
        # so we first execute the previous statements
        if len(stmts) > 1:
            exec(
                compile(
                    ast.Module(body=stmts[:-1]), filename="<ast>", mode="exec"
                ),
                globals,
                locals,
            )
        # then we eval the last one
        return eval(
            compile(
                ast.Expression(body=stmts[-1].value),
                filename="<ast>",
                mode="eval",
            ),
            globals,
            locals,
        )
    else:
        # otherwise we just execute the entire code
        return exec(script, globals, locals)


@app.cell
def _(ell, mo):
    def code_fence(code):
        return f"```python\n\n{code}\n\n```"


    @ell.tool()
    def execute_code(code: str):
        """
        Execute python. The last line should be the result, don't use print().
        Please make sure it is safe before executing.
        """
        with mo.capture_stdout() as out:
            result = exec_with_result(code)
            output = out.getvalue()
            results = [
                "**Work**",
                code_fence(code),
                "**Result**",
                code_fence(result if result is not None else output),
            ]
            return mo.md("\n\n".join(results))

    return (execute_code,)


@app.cell
def _(client, ell, execute_code, mo, model):
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

    return (my_model,)


@app.cell
def _(mo, my_model):
    numbers = [x for x in range(1, 10)]

    mo.ui.chat(
        my_model,
        prompts=[
            "What is the square root of {{number}}?",
            f"Can you sum this list using python: {numbers}",
        ],
    )
    return


if __name__ == "__main__":
    app.run()
