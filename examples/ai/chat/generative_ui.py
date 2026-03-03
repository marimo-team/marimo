# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "ell-ai==0.0.14",
#     "marimo",
#     "openai==1.53.0",
#     "polars==1.12.0",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl
    import marimo as mo
    import os
    import altair

    has_api_key = os.environ.get("OPENAI_API_KEY") is not None
    mo.stop(
        not has_api_key,
        mo.md("Please set the `OPENAI_API_KEY` environment variable").callout(),
    )

    # Grab a dataset
    df = pl.read_csv("hf://datasets/scikit-learn/Fish/Fish.csv")
    return df, mo


@app.cell
def _(df, mo):
    import ell


    @ell.tool()
    def chart_data(x_encoding: str, y_encoding: str, color: str):
        """Generate an altair chart"""
        import altair as alt

        return (
            alt.Chart(df)
            .mark_circle()
            .encode(x=x_encoding, y=y_encoding, color=color)
            .properties(width=500)
        )


    @ell.tool()
    def filter_dataset(sql_query: str):
        """
        Filter a polars dataframe using SQL. Please only use fields from the schema.
        When referring to the table in SQL, call it 'data'.
        """
        filtered = df.sql(sql_query, table_name="data")
        return mo.ui.table(
            filtered,
            label=f"```sql\n{sql_query}\n```",
            selection=None,
            show_column_summaries=False,
        )

    return chart_data, ell, filter_dataset


@app.cell
def _(chart_data, df, ell, filter_dataset, mo):
    @ell.complex(model="gpt-4o", tools=[chart_data, filter_dataset])
    def analyze_dataset(prompt: str) -> str:
        """You are a data scientist that can analyze a dataset"""
        return f"I have a dataset with schema: {df.schema}. \n{prompt}"


    def my_model(messages):
        response = analyze_dataset(messages)
        if response.tool_calls:
            return response.tool_calls[0]()
        return response.text


    mo.ui.chat(
        my_model,
        prompts=[
            "Can you chart two columns of your choosing?",
            "Can you find the min, max of all numeric fields?",
            "What is the sum of {{column}}?",
        ],
    )
    return


if __name__ == "__main__":
    app.run()
