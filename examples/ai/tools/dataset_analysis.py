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
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import ell
    from pydantic import Field
    import requests
    import altair as alt
    import pyarrow
    import polars as pl
    from vega_datasets import data

    return alt, data, ell, mo, pl


@app.cell
def _(mo):
    mo.md("""
    # Using tools with ell

    This example shows how to use [`ell`](https://docs.ell.so/) with tools to analyze a dataset and return rich responses like charts and tables.
    """)
    return


@app.cell
def _(mo):
    import os

    os_key = os.environ.get("OPENAI_API_KEY")
    input_key = mo.ui.text(label="OpenAI API key", kind="password")
    input_key if not os_key else None
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
def _(data, pl):
    cars = pl.DataFrame(data.cars())
    schema = cars.schema
    return cars, schema


@app.cell
def _(alt, cars, client, ell, schema):
    @ell.tool()
    def get_chart(
        x_encoding: str,
        y_encoding: str,
        color: str,
    ):
        """Generate an altair chart."""
        return (
            alt.Chart(cars)
            .mark_circle()
            .encode(
                x=x_encoding,
                y=y_encoding,
                color=color,
            )
            .properties(width=400)
        )


    @ell.tool()
    def get_filtered_table(sql_query: str):
        """Filter a polars dataframe using SQL. Please only use fields from the schema. When referring to the dataframe, call it 'data'."""
        print(sql_query)
        filtered = cars.sql(sql_query, table_name="data")
        return filtered


    @ell.complex(
        model="gpt-4-turbo", tools=[get_chart, get_filtered_table], client=client
    )
    def analyze_dataset(prompt: str) -> str:
        """You are an agent that can analayze the a dataset"""
        return f"I have a dataset with schema: {schema}. \n{prompt}"

    return (analyze_dataset,)


@app.cell
def _(input_key, mo, schema):
    text = mo.ui.text(
        full_width=True,
        disabled=not input_key.value,
    ).form(bordered=False)

    mo.md(f"""
    ## **Ask a question!**

    {mo.accordion({
        "View schema": schema,
        "View sample questions": mo.md('''
        * What is the relationship between Cylinders and Horsepower?"
        * How many cars with MPG great than 30?
        ''')
    })}

    {text}
    """)
    return (text,)


@app.cell
def _(analyze_dataset, mo, text):
    mo.stop(not text.value)

    with mo.status.spinner(title=f"Thinking...", subtitle=text.value):
        response = analyze_dataset(text.value)
        summary = "Nothing found"
        if response.tool_calls:
            try:
                summary = response.tool_calls[0]()
                mo.output.replace(summary)
            except Exception as e:
                mo.output.replace(mo.callout(str(e)))
    return


if __name__ == "__main__":
    app.run()
