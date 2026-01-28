import marimo

__generated_with = "0.19.6"
app = marimo.App(auto_download=["ipynb"])


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
    # fig
    return (df,)


@app.cell
def _(df, plt):
    plt.scatter(x=df["sepal_width"], y=df["sepal_length"])
    print("Plot in console output")
    # plt.show()
    return


@app.cell
def _():
    # plt.scatter(x=df["sepal_width"], y=df["sepal_length"])
    return


@app.cell
def _(mo):
    iframe = mo.iframe("""
    <div style='border: 2px solid #4CAF50; padding: 20px; border-radius: 10px; background: linear-gradient(135deg, #e0f7fa, #80deea);'>
      <h1 style='color: #00796b; font-family: Arial, sans-serif;'>Welcome to My Interactive Frame</h1>
      <p style='font-size: 16px; color: #004d40;'>This is a more complex div element with styled borders, gradients, and custom fonts.</p>
      <ul style='color: #004d40;'>
        <li>Feature 1: Stylish layout</li>
        <li>Feature 2: Custom fonts and colors</li>
        <li>Feature 3: Rounded corners and padding</li>
      </ul>
      <button style='background-color: #00796b; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;' onclick="alert('Button clicked!')">Click Me</button>
    </div>
    """)
    # iframe
    return (iframe,)


@app.cell
def _(iframe, mo):
    mo.Html(iframe.text)
    return


@app.cell
def _(mo):
    mo.iframe(
        '<iframe src="demo_iframe.html" height="200" width="300" title="Iframe Example"></iframe>'
    )
    return


@app.cell
def _(mo):
    mo.iframe(
        '<iframe id="inlineFrameExample" title="Inline Frame Example" width="800" height="600" src="https://www.openstreetmap.org/export/embed.html?bbox=-0.004017949104309083%2C51.47612752641776%2C0.00030577182769775396%2C51.478569861898606&amp;layer=mapnik"></iframe>'
    )
    return


@app.cell
def _(df):
    df
    return


@app.cell
def _(df, mo):
    mo.vstack([df, df])
    return


if __name__ == "__main__":
    app.run()
