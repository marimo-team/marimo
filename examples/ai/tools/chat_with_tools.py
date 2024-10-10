# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair==5.4.1",
#     "beautifulsoup4==4.12.3",
#     "ell-ai==0.0.13",
#     "marimo",
#     "openai==1.51.0",
#     "polars==1.9.0",
#     "pyarrow==17.0.0",
#     "pydantic==2.9.2",
#     "requests==2.32.3",
#     "vega-datasets==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.9.4"
app = marimo.App(width="full")


@app.cell
def __():
    import marimo as mo
    import ell
    import requests
    import altair as alt
    import pyarrow
    import polars as pl
    from bs4 import BeautifulSoup
    from vega_datasets import data
    return BeautifulSoup, alt, data, ell, mo, pl, pyarrow, requests


@app.cell
def __(mo):
    mo.md(
        """
        # Using tools with ell

        This example shows how to use [`ell`](https://docs.ell.so/) with tools to analyze a dataset and return rich responses like charts and tables.
        """
    )
    return


@app.cell
def __(mo):
    mo.md(r"""## Setup""")
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

    import openai

    client = openai.Client(api_key=openai_key)

    mo.stop(
        not openai_key,
        mo.md(
            "Please set the `OPENAI_API_KEY` environment variable or provide it in the input field"
        ),
    )
    return client, openai, openai_key


@app.cell
def __(mo):
    get_dataset, set_dataset = mo.state("cars")
    return get_dataset, set_dataset


@app.cell
def __():
    # data.list_datasets()
    return


@app.cell
def __(get_dataset, mo, set_dataset):
    options = [
        "cars",
        "barley",
        "countries",
        "disasters",
    ]
    dataset_dropdown = mo.ui.dropdown(
        options, label="Datasets", value=get_dataset(), on_change=set_dataset
    )
    return dataset_dropdown, options


@app.cell
def __(data, dataset_dropdown, pl):
    selected_dataset = dataset_dropdown.value
    df = pl.DataFrame(data.__call__(selected_dataset))
    return df, selected_dataset


@app.cell
def __(mo):
    mo.md(r"""## Defining tools""")
    return


@app.cell
def __():
    # https://stackoverflow.com/questions/33908794/get-value-of-last-expression-in-exec-call
    def custom_exec(script, globals=None, locals=None):
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
    return (custom_exec,)


@app.cell
def __(
    BeautifulSoup,
    alt,
    client,
    custom_exec,
    dataset_dropdown,
    df,
    ell,
    get_dataset,
    mo,
    requests,
):
    @ell.tool()
    def show_dataset_selector():
        """Ask the user to select a dataset"""
        return dataset_dropdown


    @ell.tool()
    def get_chart(
        x_encoding: str,
        y_encoding: str,
        color: str,
    ):
        """Generate an altair chart. For each encoding, you can customize the type or aggregation function, such as year:Q or year:T or year:N"""
        return (
            alt.Chart(df)
            .mark_circle()
            .encode(
                x=x_encoding,
                y=y_encoding,
                color=color,
            )
            .properties(width="container")
        )


    @ell.tool()
    def get_filtered_table(sql_query: str):
        """Filter a polars dataframe using SQL. Please only use fields from the schema. When referring to the dataframe, call it 'data'."""
        print(sql_query)
        filtered = df.sql(sql_query, table_name="data")
        return filtered


    @ell.tool()
    def execute_code(code: str):
        """
        Execute python. Please make sure it is safe before executing. Otherwise do not choose this tool.
        The python must be executable on one line
        """
        try:
            return mo.md(f"""
    ```python

    {code}

    ```

    {custom_exec(code)}
            """)
        except Exception as e:
            return f"Failed to execute code: {code}"


    @ell.simple(model="gpt-4-turbo", client=client)
    def rag(content: str, question: str):
        """
        Given some content, answer a question about it.
        """
        return f"Content: {content}. Question: {question}"


    @ell.tool()
    def search_the_web(search_query: str, question: str):
        """
        Search the web with a give search query and question
        """

        response = requests.get(
            "https://google.com/search", params={"q": search_query}
        )
        soup = BeautifulSoup(response.text, "html.parser")
        return rag(soup.get_text(), question)


    @ell.complex(
        model="gpt-4-turbo",
        tools=[
            get_chart,
            get_filtered_table,
            execute_code,
            search_the_web,
            show_dataset_selector,
        ],
        client=client,
    )
    def custom_chatbot(messages, config) -> str:
        message_history = [
            ell.user(message.content)
            if message.role == "user"
            else ell.assistant(message.content)
            for message in messages
        ]

        return [
            ell.system(
                f"""
                You are a chatbot with many tools. Choose a tool or response with markdown-compatible text.

                If you are talking about a dataset, the current dataset is {get_dataset()}, with schema: {df.schema}
                """
            ),
        ] + message_history
    return (
        custom_chatbot,
        execute_code,
        get_chart,
        get_filtered_table,
        rag,
        search_the_web,
        show_dataset_selector,
    )


@app.cell
def __(custom_chatbot, mo):
    def handle_messages(messages):
        response = custom_chatbot(messages, {})
        if response.tool_calls:
            tool = response.tool_calls[0]
            tool_response = tool()
            return mo.vstack([f"Tool used: {str(tool.tool)}", tool_response])
        return mo.md(response.text)


    mo.ui.chat(handle_messages)
    return (handle_messages,)


if __name__ == "__main__":
    app.run()
