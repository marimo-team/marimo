import marimo

__generated_with = "0.18.4"
app = marimo.App(auto_download=["ipynb"])


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import plotly.express as px
    return mo, plt, px


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    This notebook contains:

    - Markdown
    - a marimo UI element
    - a Plotly scatter plot
    - a matplotlib plot
    - a dataframe output

    This Markdown also contains some math: $f(x)$

    \[
    g(x) = 0
    \]
    """)
    return


@app.cell
def _(mo):
    mo.ui.text(label="$f(x)$")
    return


@app.cell
def _():
    # How are errors serialized?
    1 / 0
    return


@app.cell
def _():
    print("This is console output") 
    return



@app.cell
def _(px):
    df = px.data.iris()
    fig = px.scatter(
        df, x="sepal_width", y="sepal_length", color="species", symbol="species"
    )
    fig
    return (df,)


@app.cell
def _(df, plt):
    plt.scatter(x=df["sepal_width"], y=df["sepal_length"])
    return


@app.cell
def _(df):
    df
    return


if __name__ == "__main__":
    app.run()
