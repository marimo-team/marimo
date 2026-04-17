# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "pandas==2.3.3",
#     "plotly==6.5.1",
# ]
# ///

import marimo

__generated_with = "0.20.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import plotly.graph_objects as go

    return go, mo, pd


@app.cell
def _(mo):
    mo.md("""
    # Reactive Plotly Waterfall Chart Selection

    This example demonstrates reactive waterfall chart selections with `mo.ui.plotly`.

    Waterfall charts (also called bridge charts) decompose a starting value into
    its contributing increments, making it easy to trace how individual drivers
    move a KPI from one level to another.

    Each bar has a **measure** type:
    - **`absolute`** — starts at zero and sets the running total
    - **`relative`** — adds to (or subtracts from) the running total
    - **`total`** — shows the current running total as a reference bar

    Try:
    - **Click** any bar to select it
    - **Drag a box** over multiple bars to select a range
    - Watch the detail panel and table update reactively
    """)
    return


@app.cell
def _(go, mo):
    mo.md("## Annual P&L Bridge")

    fig_pl = go.Figure(
        go.Waterfall(
            name="P&L",
            orientation="v",
            measure=[
                "absolute",
                "relative",
                "relative",
                "relative",
                "relative",
                "total",
                "relative",
                "relative",
                "total",
            ],
            x=[
                "Revenue",
                "COGS",
                "Gross Profit",
                "R&D",
                "S&M",
                "EBITDA",
                "D&A",
                "Tax",
                "Net Income",
            ],
            y=[4_200, -1_500, 0, -420, -310, 0, -180, -240, 0],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            increasing={"marker": {"color": "#2a9d8f"}},
            decreasing={"marker": {"color": "#e76f51"}},
            totals={"marker": {"color": "#264653", "line": {"color": "#264653"}}},
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Value: $%{y:,.0f}K<br>"
                "<extra></extra>"
            ),
        )
    )
    fig_pl.update_layout(
        title="Annual P&L Bridge — click or box-select bars",
        yaxis_title="USD (thousands)",
        dragmode="select",
        showlegend=False,
    )

    pl_plot = mo.ui.plotly(fig_pl)
    pl_plot
    return (pl_plot,)


@app.cell
def _(mo, pl_plot):
    _pts = pl_plot.value

    if _pts:
        _total = sum(
            p["y"] for p in _pts
            if isinstance(p.get("y"), (int, float)) and p.get("measure") != "total"
        )
        _names = ", ".join(p["x"] for p in _pts if p.get("x"))
        _detail = (
            f"**{len(_pts)} bar(s) selected:** {_names}  \n"
            f"Net relative contribution: **${_total:,.0f}K**"
        )
    else:
        _detail = "Click or drag to select bars."

    mo.md(f"""
    ### Selection Detail

    {_detail}

    **Indices:** {pl_plot.indices}

    **Raw value:** {pl_plot.value}
    """)
    return


@app.cell
def _(go, mo):
    mo.md("## Regional Sales Waterfall — Multi-Trace")

    fig_regional = go.Figure()

    traces = [
        ("North America", [800, 120, -40, 0], "#2a9d8f"),
        ("Europe",        [600,  80, -55, 0], "#e9c46a"),
        ("Asia-Pacific",  [450,  95, -30, 0], "#e76f51"),
    ]
    measures = ["absolute", "relative", "relative", "total"]
    x_labels = ["Baseline", "Growth", "Churn", "Net"]

    for region, values, colour in traces:
        fig_regional.add_trace(
            go.Waterfall(
                name=region,
                measure=measures,
                x=x_labels,
                y=values,
                offsetgroup=region,
                increasing={"marker": {"color": colour}},
                totals={"marker": {"color": colour}},
            )
        )

    fig_regional.update_layout(
        title="Regional Sales Bridge — select bars across traces",
        yaxis_title="Revenue ($M)",
        barmode="group",
        dragmode="select",
    )

    regional_plot = mo.ui.plotly(fig_regional)
    regional_plot
    return (regional_plot,)


@app.cell
def _(mo, pd, regional_plot):
    _pts = regional_plot.value

    if _pts:
        _rows = pd.DataFrame(
            [
                {
                    "Stage": p.get("x"),
                    "Region": p.get("name"),
                    "Value ($M)": p.get("y"),
                    "Type": p.get("measure"),
                }
                for p in _pts
                if p
            ]
        )
    else:
        _rows = pd.DataFrame(columns=["Stage", "Region", "Value ($M)", "Type"])

    mo.vstack([
        mo.md(f"**{len(_pts)} bar(s) selected** | Indices: {regional_plot.indices}"),
        mo.ui.table(_rows),
    ])
    return


@app.cell
def _(go, mo):
    mo.md("## Horizontal Budget Waterfall")

    fig_h = go.Figure(
        go.Waterfall(
            orientation="h",
            measure=["absolute", "relative", "relative", "relative", "total"],
            y=["Budget", "Savings", "Overspend", "Reserve", "Actual"],
            x=[500, -80, 120, -30, 0],
            connector={"mode": "between", "line": {"width": 1, "color": "rgb(180,180,180)"}},
            increasing={"marker": {"color": "#e76f51"}},
            decreasing={"marker": {"color": "#2a9d8f"}},
            totals={"marker": {"color": "#457b9d"}},
            hovertemplate="<b>%{y}</b><br>Amount: $%{x:,.0f}K<extra></extra>",
        )
    )
    fig_h.update_layout(
        title="Budget vs Actual — horizontal bridge",
        xaxis_title="USD (thousands)",
        dragmode="select",
        showlegend=False,
    )

    h_plot = mo.ui.plotly(fig_h)
    h_plot
    return (h_plot,)


@app.cell
def _(h_plot, mo):
    _pts = h_plot.value

    if _pts:
        _names = [p.get("y") for p in _pts if p.get("y")]
        _summary = f"Selected: **{', '.join(_names)}**"
    else:
        _summary = "Click or drag to select budget items."

    mo.md(f"""
    ### Horizontal Selection

    {_summary}

    **Indices:** {h_plot.indices}
    """)
    return


if __name__ == "__main__":
    app.run()
