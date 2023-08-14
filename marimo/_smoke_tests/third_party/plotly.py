# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __():
    import plotly.express as px

    px.scatter(x=[0, 1, 2, 3, 4], y=[0, 1, 4, 9, 16])
    return (px,)


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
def __(fig):
    fig
    return


if __name__ == "__main__":
    app.run()
