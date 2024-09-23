# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "plotly==5.24.1",
#     "pandas==2.2.3",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.8.18"
app = marimo.App(width="full")


@app.cell
def __(mo):
    mo.md("""# Plotly Express Chart""")
    return


@app.cell
def __():
    import plotly.express as px

    px.scatter(x=[0, 1, 2, 3, 4], y=[0, 1, 4, 9, 16])
    return (px,)


@app.cell
def __(mo, px):
    plot = mo.ui.plotly(
        px.scatter(x=[0, 1, 2, 3, 4], y=[0, 1, 4, 9, 16], width=600)
    )
    mo.vstack(
        [
            mo.md("# Fixed width"),
            plot,
        ]
    )
    return (plot,)


@app.cell
def __(mo, plot):
    mo.vstack(
        [
            mo.hstack(
                [
                    mo.ui.table(plot.value, label="Points", selection=None),
                    mo.ui.table(
                        [
                            {"start": r[0], "end": r[1], "axis": key}
                            for key, r in plot.ranges.items()
                        ],
                        selection=None,
                        label="Ranges",
                    ),
                ],
                widths="equal",
            ),
            plot.indices,
        ]
    )
    return


@app.cell
def __(mo):
    mo.md("""# Plotly Graph Objects Chart""")
    return


@app.cell
def __(mo):
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

    plot2 = mo.ui.plotly(fig)
    plot2
    return contestant, df, fig, go, group, pd, plot2


@app.cell
def __(mo, plot2):
    mo.ui.table(plot2.value, selection=None)
    return


@app.cell
def __(mo):
    mo.md("""# Re-rendering Chart""")
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
    return (sample_size,)


@app.cell
def __(cars, mo, px, sample_size):
    _fig = px.scatter(
        cars.sample(sample_size.value),
        x="Horsepower",
        y="Miles_per_Gallon",
        color="Origin",
        size="Weight_in_lbs",
        hover_data=["Name", "Origin"],
    )

    _fig
    plot3 = mo.ui.plotly(_fig)
    plot3
    return (plot3,)


@app.cell
def __(mo, plot3):
    mo.ui.table(plot3.value, selection=None)
    return


@app.cell
def __(mo):
    mo.md("""# 3D Chart""")
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
