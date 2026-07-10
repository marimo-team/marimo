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
    import plotly.express as px
    import plotly.graph_objects as go

    return go, mo, pd, px


@app.cell
def _(mo):
    mo.md("""
    # Reactive Plotly Funnel Chart Selection

    This example demonstrates reactive funnel chart selections with `mo.ui.plotly`.

    Funnel charts visualise drop-off at each stage of a sequential process (e.g. a
    sales pipeline or marketing funnel).  Each segment represents one stage; the bar
    width shows the absolute count and the percent metrics show retention relative to
    the initial, previous, and overall totals.

    Try:
    - **Click** any funnel stage to select it — the table below updates instantly
    - **Drag a box** (set `dragmode="select"`) over multiple stages to select a range
    - Switch between the multi-trace and `FunnelArea` tabs to explore variants
    """)
    return


@app.cell
def _(pd):
    pipeline_data = pd.DataFrame(
        {
            "stage": [
                "Leads",
                "Qualified",
                "Proposal",
                "Negotiation",
                "Closed Won",
            ],
            "count": [5000, 2800, 1400, 620, 310],
            "region": ["Global"] * 5,
        }
    )
    return (pipeline_data,)


@app.cell
def _(mo, pipeline_data, px):
    mo.md("## Single-Trace Funnel (`px.funnel`)")

    fig_funnel = px.funnel(
        pipeline_data,
        x="count",
        y="stage",
        title="Sales Pipeline — click a stage to inspect it",
        labels={"count": "Leads", "stage": "Stage"},
    )
    fig_funnel.update_layout(
        dragmode="select",
        margin=dict(l=120),
    )

    funnel_plot = mo.ui.plotly(fig_funnel)
    funnel_plot
    return (funnel_plot,)


@app.cell
def _(funnel_plot, mo, pipeline_data):
    _pts = funnel_plot.value

    if _pts:
        _stage = _pts[0].get("y") or _pts[0].get("label")
        _row = pipeline_data[pipeline_data["stage"] == _stage]
        _pct_initial = _pts[0].get("percentInitial", 1.0)
        _summary = (
            f"**{_stage}** — "
            f"{_row['count'].iloc[0]:,} leads — "
            f"{_pct_initial:.0%} retention from start"
        )
    else:
        _summary = "Click any funnel stage to inspect it."

    mo.md(f"""
    ### Selected Stage

    {_summary}

    **Raw selection:** {funnel_plot.value}
    """)
    return


@app.cell
def _(mo, pd):
    mo.md("## Multi-Trace Funnel — Regional Breakdown")

    regional = pd.DataFrame(
        {
            "stage": [
                "Leads", "Qualified", "Proposal", "Negotiation", "Closed Won",
                "Leads", "Qualified", "Proposal", "Negotiation", "Closed Won",
            ],
            "count": [3000, 1600, 900, 380, 190, 2000, 1200, 500, 240, 120],
            "region": ["North America"] * 5 + ["Europe"] * 5,
        }
    )
    return (regional,)


@app.cell
def _(mo, px, regional):
    fig_regional = px.funnel(
        regional,
        x="count",
        y="stage",
        color="region",
        title="Regional Pipeline — select stages to compare regions",
    )
    fig_regional.update_layout(dragmode="select")

    regional_plot = mo.ui.plotly(fig_regional)
    regional_plot
    return (regional_plot,)


@app.cell
def _(mo, regional, regional_plot):
    _pts = regional_plot.value

    if _pts:
        _rows = regional[
            regional["stage"].isin(
                [p.get("y") or p.get("label") for p in _pts if p]
            )
        ]
        _table = mo.ui.table(_rows.reset_index(drop=True))
    else:
        _table = mo.ui.table(regional.iloc[0:0])

    mo.vstack([
        mo.md(f"**{len(_pts)} stage(s) selected** | Indices: {regional_plot.indices}"),
        _table,
    ])
    return


@app.cell
def _(go, mo):
    mo.md("## Funnel Area Chart (`go.Funnelarea`)")

    fig_area = go.Figure(
        go.Funnelarea(
            labels=["Awareness", "Interest", "Consideration", "Intent", "Purchase"],
            values=[10000, 6000, 3000, 1200, 400],
            textinfo="label+percent",
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Count: %{value:,}<br>"
                "Retention from start: %{percentInitial:.1%}<br>"
                "Retention from previous: %{percentPrevious:.1%}"
                "<extra></extra>"
            ),
        )
    )
    fig_area.update_layout(title="Marketing Funnel Area — click a segment")

    area_plot = mo.ui.plotly(fig_area)
    area_plot
    return (area_plot,)


@app.cell
def _(area_plot, mo):
    _pts = area_plot.value

    if _pts:
        _p = _pts[0]
        _detail = (
            f"**{_p.get('label')}** — "
            f"{_p.get('value', 0):,} users — "
            f"{_p.get('percentInitial', 1.0):.1%} of total"
        )
    else:
        _detail = "Click any segment to inspect it."

    mo.md(f"""
    ### Selected Segment

    {_detail}

    **Raw selection:** {area_plot.value}
    """)
    return


if __name__ == "__main__":
    app.run()
