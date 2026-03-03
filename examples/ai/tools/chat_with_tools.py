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

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import ell
    import requests
    import altair as alt
    import pyarrow
    import polars as pl
    from bs4 import BeautifulSoup
    from vega_datasets import data

    return BeautifulSoup, alt, data, ell, mo, pl, requests


@app.cell
def _(mo):
    mo.md("""
    # Creating rich tools with ell

    This example shows how to use [`ell`](https://docs.ell.so/) with tools to analyze a dataset and return rich responses like charts and tables.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Setup
    """)
    return


@app.cell
def _(mo):
    import os

    os_key = os.environ.get("OPENAI_API_KEY")
    input_key = mo.ui.text(
        label="OpenAI API key",
        kind="password",
        value=os.environ.get("OPENAI_API_KEY", ""),
    )
    input_key
    return input_key, os_key


@app.cell
def _(input_key, mo, os_key):
    openai_key = os_key or input_key.value

    import openai

    client = openai.Client(api_key=openai_key)

    mo.stop(
        not openai_key,
        mo.md(
            "Please set the `OPENAI_API_KEY` environment variable or provide it in the input field"
        ),
    )
    return (client,)


@app.cell
def _(mo):
    get_dataset, set_dataset = mo.state("cars")
    return get_dataset, set_dataset


@app.cell
def _(get_dataset, mo, set_dataset):
    options = ["cars", "barley", "countries", "disasters"]
    dataset_dropdown = mo.ui.dropdown(
        options, label="Datasets", value=get_dataset(), on_change=set_dataset
    )
    return (dataset_dropdown,)


@app.cell
def _(data, dataset_dropdown, pl):
    selected_dataset = dataset_dropdown.value
    df = pl.DataFrame(data.__call__(selected_dataset))
    return (df,)


@app.cell
def _(mo):
    mo.md(r"""
    ## Defining tools
    """)
    return


@app.function
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


@app.cell
def _(BeautifulSoup, alt, client, dataset_dropdown, df, ell, mo, requests):
    @ell.tool()
    def show_dataset_selector():
        """Ask the user to select a dataset"""
        return dataset_dropdown


    @ell.tool()
    def chart_data(
        x_encoding: str,
        y_encoding: str,
        color: str,
    ):
        """Generate an altair chart. For each encoding, you can customize the type or aggregation function, such as year:Q or year:T or year:N"""
        return (
            alt.Chart(df)
            .mark_circle()
            .encode(x=x_encoding, y=y_encoding, color=color)
            .properties(width=500)
        )


    @ell.tool()
    def filter_dataset_with_sql(sql_query: str):
        """
        Filter a polars dataframe using SQL. Please only use fields from the schema.
        When referring to the dataframe, call it 'data'."""
        filtered = df.sql(sql_query, table_name="data")
        return mo.ui.table(filtered, selection=None, label=sql_query)


    @ell.tool()
    def execute_code(code: str):
        """
        Execute python. Please make sure it is safe before executing.
        Otherwise do not choose this tool.
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


    TOOLS = [
        chart_data,
        filter_dataset_with_sql,
        execute_code,
        search_the_web,
        show_dataset_selector,
    ]

    tool_docs = {}
    for tool in TOOLS:
        tool_docs[tool.__name__] = tool.__doc__

    mo.accordion(tool_docs)
    return (TOOLS,)


@app.cell
def _(TOOLS, client, df, ell, get_dataset, mo):
    @ell.complex(
        model="gpt-4-turbo",
        tools=TOOLS,
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
                You are a chatbot with many tools. Choose a tool or respond with markdown-compatible text.
                If you are talking about a dataset, the current dataset is {get_dataset()}, with schema:{df.schema}
                """
            ),
        ] + message_history


    def model(messages):
        response = custom_chatbot(messages, {})
        if response.tool_calls:
            tool = response.tool_calls[0]
            tool_response = tool()
            return mo.vstack(
                [mo.md(f"Tool used: **{str(tool.tool.__name__)}**"), tool_response]
            )
        return mo.md(response.text)

    return (model,)


@app.cell
def _(mo, model):
    mo.ui.chat(
        model,
        prompts=[
            "I'd like to analyze a dataset can you give me some options",
            "Can you describe this dataset",
            "Let's plot {{x}} vs {{y}}",
        ],
    )
    return


if __name__ == "__main__":
    app.run()
