import marimo

__generated_with = "0.19.5"
app = marimo.App(width="medium", auto_download=["html"])

with app.setup:
    import marimo as mo
    import pandas as pd
    import plotly.graph_objects as go


@app.cell
def _():
    df_mock = pd.DataFrame(
        {
            "id": ["WC_0001", "WC_0002", "WC_0003", "WC_0004", "WC_0005"],
            "Region": ["WC", "WC", "WC", "WC", "WC"],
            "lon": [18.42, 18.46, 18.50, 18.54, 18.58],
            "lat": [-33.93, -33.95, -33.91, -33.97, -33.89],
            "cluster": [0, 1, 0, 2, 1],
        }
    )

    figg = go.Figure()

    figg.add_trace(
        go.Scattermap(
            lon=df_mock["lon"],
            lat=df_mock["lat"],
            mode="markers",
            marker=dict(size=12, color="red", opacity=0.9),
            customdata=df_mock[["id", "cluster"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "cluster: %{customdata[1]}<br>"
                "<extra></extra>"
            ),
            name="Mock sites",
        )
    )

    figg.update_layout(
        dragmode="lasso",
        map=dict(
            style="open-street-map",
            zoom=10,
            center=dict(lat=df_mock["lat"].mean(), lon=df_mock["lon"].mean()),
        ),
        margin=dict(l=0, r=0, t=0, b=0),
    )

    plot = mo.ui.plotly(figg)
    plot
    return (plot,)


@app.cell
def _(plot):
    plot.value
    return


if __name__ == "__main__":
    app.run()
