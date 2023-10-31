# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.39"
app = marimo.App(width="full")


@app.cell
def __(mo):
    mo.md("# Plotly Express Chart")
    return


@app.cell
def __():
    import plotly.express as px

    px.scatter(x=[0, 1, 2, 3, 4], y=[0, 1, 4, 9, 16])
    return px,


@app.cell
def __(mo, px):
    mo.vstack(
        [
            mo.md("# Fixed width"),
            px.scatter(x=[0, 1, 2, 3, 4], y=[0, 1, 4, 9, 16], width=600),
        ]
    )
    return


@app.cell
def __(mo):
    mo.md("# Plotly Graph Objects Chart")
    return


@app.cell
def __():
    import pandas as pd
    import plotly.graph_objects as go

    df = pd.DataFrame(
        {
            "Fruit": [
                "Apples",
                "Oranges",
                "Bananas",
                "Apples",
                "Oranges",
                "Bananas",
            ],
            "Contestant": [
                "Alex",
                "Alex",
                "Alex",
                "Jordan",
                "Jordan",
                "Jordan",
            ],
            "Number Eaten": [2, 1, 3, 1, 3, 2],
        }
    )

    fig = go.Figure()
    for contestant, group in df.groupby("Contestant"):
        fig.add_trace(
            go.Bar(
                x=group["Fruit"],
                y=group["Number Eaten"],
                name=contestant,
                hovertemplate=(
                    "Contestant=%s<br>Fruit=%%{x}<br>"
                    "Number Eaten=%%{y}<extra></extra>"
                )
                % contestant,
            )
        )
    fig.update_layout(legend_title_text="Contestant")
    fig.update_xaxes(title_text="Fruit")
    fig.update_yaxes(title_text="Number Eaten")

    fig
    return contestant, df, fig, go, group, pd


@app.cell
def __(mo):
    mo.md("# Re-rendering Chart")
    return


@app.cell
def __():
    import vega_datasets as datasets
    import marimo as mo

    cars = datasets.data.cars()
    return cars, datasets, mo


@app.cell
def __(cars, mo):
    sample_size = mo.ui.slider(label="Sample", start=100, stop=len(cars), step=100)
    sample_size
    return sample_size,


@app.cell
def __(cars, px, sample_size):
    _fig = px.scatter(
        cars.sample(sample_size.value),
        x="Horsepower",
        y="Miles_per_Gallon",
        color="Origin",
        size="Weight_in_lbs",
        hover_data=["Name"],
    )

    _fig
    return


@app.cell
def __(mo):
    mo.md("# 3D Chart")
    return


@app.cell
def __(go, pd):
    # load dataset
    _df = pd.read_csv(
        "https://raw.githubusercontent.com/plotly/datasets/master/volcano.csv"
    )

    # create figure
    _fig = go.Figure()

    # Add surface trace
    _fig.add_trace(go.Surface(z=_df.values.tolist(), colorscale="Viridis"))

    # Update plot sizing
    _fig.update_layout(
        width=800,
        height=900,
        autosize=False,
        margin=dict(t=0, b=0, l=0, r=0),
        template="plotly_white",
    )

    # Update 3D scene options
    _fig.update_scenes(aspectratio=dict(x=1, y=1, z=0.7), aspectmode="manual")

    # Add dropdown
    _fig.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                direction="left",
                buttons=list(
                    [
                        dict(
                            args=["type", "surface"],
                            label="3D Surface",
                            method="restyle",
                        ),
                        dict(
                            args=["type", "heatmap"],
                            label="Heatmap",
                            method="restyle",
                        ),
                    ]
                ),
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0.11,
                xanchor="left",
                y=1.1,
                yanchor="top",
            ),
        ]
    )

    # Add annotation
    _fig.update_layout(
        annotations=[
            dict(
                text="Trace type:",
                showarrow=False,
                x=0,
                y=1.08,
                yref="paper",
                align="left",
            )
        ]
    )

    _fig
    return


if __name__ == "__main__":
    app.run()
