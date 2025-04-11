import marimo

__generated_with = "0.12.8"
app = marimo.App(width="full")


@app.cell
def _():
    import plotly.express as px
    fig = px.scatter(x=[0, 1, 2, 3, 4], y=[0, 1, 4, 9, 16])
    fig.show()
    return fig, px


if __name__ == "__main__":
    app.run()
