

import marimo

__generated_with = "0.13.0"
app = marimo.App()


@app.cell
def _():
    import plotly.graph_objects as go

    # mo.md(f"```\n{foo=!r}\n{bar=!r}\n```"),
    go.Figure()
    return


@app.cell
def _():
    import marimo as mo
    import plotly.express as px


    px.line(
        x=[1, 2, 3, 4],
        y=[1, 4, 9, 16],
        title=r"$\alpha_{1c} = 352 \pm 11 \text{ km s}^{-1}$",
    ).update_layout(
        xaxis_title=r"$\sqrt{(n_\text{c}(t|{T_\text{early}}))}$",
        yaxis_title=r"$d, r \text{ (solar radius)}$",
    )
    return


if __name__ == "__main__":
    app.run()
