import marimo

__generated_with = "0.19.4"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import plotly.express as px
    return mo, plt, px


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    This notebook contains:

    - Markdown
    - a marimo UI element
    - a Plotly scatter plot
    - a matplotlib plot
    - a dataframe output
    - an iframe

    This Markdown also contains some math: $f(x)$

    $$
    g(x) = 0
    $$
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
    print("Plot in console output")
    plt.show()
    return


@app.cell
def _(df, plt):
    plt.scatter(x=df["sepal_width"], y=df["sepal_length"])
    return


@app.cell
def _(df):
    df
    return


@app.cell
def _(mo):
    html = "<h1>Hello, world!</h1>"
    mo.iframe(html)
    return


@app.cell
def _(mo):
    mo.Html("""<iframe width="420" height="315"
    src="https://www.youtube.com/embed/tgbNymZ7vqY">
    </iframe>""")
    return


@app.cell
def _(plt):
    sample_fig, ax = plt.subplots()
    ax.set_title("Sample Matplotlib Figure")
    ax.set_xlabel("X Axis")
    ax.set_ylabel("Y Axis")
    ax.plot([1, 2, 3, 4], [10, 20, 25, 30], label="Line 1", color="blue")
    ax.legend()
    plt.gca()
    return


@app.cell
def _(mo, plt):
    mo.mpl.interactive(plt.gcf())
    return


if __name__ == "__main__":
    app.run()
