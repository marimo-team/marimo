import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import plotly.graph_objects as go
    import numpy as np

    # 1. Create your heatmap data
    z = np.random.rand(10, 10) * 100

    # 2. Create the plotly figure
    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
            y=[
                "Mon",
                "Tue",
                "Wed",
                "Thu",
                "Fri",
                "Sat",
                "Sun",
                "Mon2",
                "Tue2",
                "Wed2",
            ],
            colorscale="Viridis",
        )
    )

    # 3. Wrap it with mo.ui.plotly
    heatmap = mo.ui.plotly(fig)

    heatmap
    return heatmap, mo


@app.cell
def _(heatmap, mo):
    # 4. Display it
    mo.md(f"""
    ## Sales Heatmap

    {heatmap}

    ### Selected Cells:
    {heatmap.value}
    """)
    return


if __name__ == "__main__":
    app.run()
