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
    # Reactive Plotly Strip Chart Selection

    This example demonstrates reactive strip chart selections with `mo.ui.plotly`.

    Strip charts (also called dot plots or jitter plots) show every individual data
    point, making them ideal for small-to-medium datasets where you want to see the
    full distribution without aggregation.

    Try:
    - **Drag a box or lasso** over points to select a subset
    - **Click** an individual point to select it
    - Watch the table and stats below update in real time

    The `customdata` field embeds `sample_id` so selected points map back to the
    source DataFrame without relying on raw indices.
    """)
    return


@app.cell
def _(pd):
    rows = [
        ("ENG-01", "Engineering", "Day",   "West",    72),
        ("ENG-02", "Engineering", "Day",   "West",    78),
        ("ENG-03", "Engineering", "Day",   "East",    81),
        ("ENG-04", "Engineering", "Night", "East",    75),
        ("ENG-05", "Engineering", "Night", "West",    84),
        ("ENG-06", "Engineering", "Night", "Central", 89),
        ("SAL-01", "Sales",       "Day",   "West",    61),
        ("SAL-02", "Sales",       "Day",   "Central", 66),
        ("SAL-03", "Sales",       "Day",   "East",    70),
        ("SAL-04", "Sales",       "Night", "West",    64),
        ("SAL-05", "Sales",       "Night", "East",    73),
        ("SAL-06", "Sales",       "Night", "Central", 77),
        ("SUP-01", "Support",     "Day",   "East",    58),
        ("SUP-02", "Support",     "Day",   "Central", 62),
        ("SUP-03", "Support",     "Day",   "West",    68),
        ("SUP-04", "Support",     "Night", "East",    60),
        ("SUP-05", "Support",     "Night", "Central", 65),
        ("SUP-06", "Support",     "Night", "West",    71),
    ]
    df = pd.DataFrame(rows, columns=["sample_id", "team", "shift", "region", "score"])
    df["passed"] = df["score"] >= 75
    return (df,)


@app.cell
def _():
    def selected_rows(selection, data):
        """Map a mo.ui.plotly selection back to rows in the source DataFrame."""
        empty = data.iloc[0:0].copy()
        if not selection:
            return empty

        # Prefer sample_id embedded via customdata.
        # Fallback-path selections embed sample_id as customdata[0] (a
        # list/tuple), not as a parsed top-level key.
        ids = []
        for row in selection:
            if isinstance(row.get("sample_id"), str):
                ids.append(row["sample_id"])
            else:
                cd = row.get("customdata")
                if isinstance(cd, (list, tuple)) and cd and isinstance(cd[0], str):
                    ids.append(cd[0])
        if ids:
            return (
                data[data["sample_id"].isin(ids)]
                .drop_duplicates("sample_id")
                .sort_values("sample_id")
            )

        # Fall back to pointIndex
        indices = sorted({
            row["pointIndex"]
            for row in selection
            if isinstance(row.get("pointIndex"), int)
            and 0 <= row["pointIndex"] < len(data)
        })
        if indices:
            return data.iloc[indices].copy()

        return empty

    return (selected_rows,)


@app.cell
def _(df, mo, px):
    mo.md("## Strip Chart (px.strip)")

    fig_strip = px.strip(
        df,
        x="team",
        y="score",
        color="shift",
        custom_data=["sample_id", "shift", "region", "passed"],
        title="Score by Team — drag a box or click individual points",
        labels={"score": "Score", "team": "Team", "shift": "Shift"},
    )
    fig_strip.update_traces(
        marker=dict(size=10, opacity=0.8),
        hovertemplate=(
            "sample_id=%{customdata[0]}<br>"
            "team=%{x}<br>"
            "score=%{y}<br>"
            "shift=%{customdata[1]}<br>"
            "region=%{customdata[2]}<br>"
            "passed=%{customdata[3]}<extra></extra>"
        ),
    )
    fig_strip.update_layout(dragmode="select")

    strip_plot = mo.ui.plotly(fig_strip)
    strip_plot
    return (strip_plot,)


@app.cell
def _(df, mo, selected_rows, strip_plot):
    _sel = selected_rows(strip_plot.value, df)

    _summary = (
        f"{len(_sel)} rows selected — "
        f"avg score: {_sel['score'].mean():.1f} — "
        f"pass rate: {_sel['passed'].mean():.0%}"
        if not _sel.empty
        else "No rows selected yet."
    )

    mo.md(f"""
    ### Strip Chart Selection

    **{_summary}**

    **Indices:** {strip_plot.indices}

    **Range:** {strip_plot.ranges}
    """)
    return


@app.cell
def _(df, mo, selected_rows, strip_plot):
    mo.ui.table(selected_rows(strip_plot.value, df))
    return


@app.cell
def _(df, go, mo):
    mo.md("## Single-Trace Strip Chart (go.Box with boxpoints='all')")

    fig_single = go.Figure(
        data=go.Box(
            x=df["team"],
            y=df["score"],
            boxpoints="all",
            jitter=0.4,
            pointpos=0,
            fillcolor="rgba(0,0,0,0)",
            line=dict(color="rgba(0,0,0,0)"),
            marker=dict(size=10, opacity=0.8, color="#e76f51"),
            customdata=df[["sample_id", "shift", "region", "passed"]],
            hovertemplate=(
                "sample_id=%{customdata[0]}<br>"
                "team=%{x}<br>"
                "score=%{y}<br>"
                "shift=%{customdata[1]}<br>"
                "region=%{customdata[2]}<br>"
                "passed=%{customdata[3]}<extra></extra>"
            ),
            name="score",
        )
    )
    fig_single.update_layout(
        title="Score by Team (single trace) — select any points",
        xaxis_title="Team",
        yaxis_title="Score",
        dragmode="select",
        showlegend=False,
    )

    strip_single = mo.ui.plotly(fig_single)
    strip_single
    return (strip_single,)


@app.cell
def _(df, mo, selected_rows, strip_single):
    _sel_s = selected_rows(strip_single.value, df)

    _summary_s = (
        f"{len(_sel_s)} rows — avg score: {_sel_s['score'].mean():.1f} — "
        f"pass rate: {_sel_s['passed'].mean():.0%}"
        if not _sel_s.empty
        else "No rows selected yet."
    )

    mo.md(f"""
    ### Single-Trace Selection

    **{_summary_s}**

    **Indices:** {strip_single.indices}
    """)
    return


@app.cell
def _(df, mo, selected_rows, strip_single):
    mo.ui.table(selected_rows(strip_single.value, df))
    return


@app.cell
def _(df, go, mo):
    mo.md("## Horizontal Strip Chart")

    fig_horizontal = go.Figure(
        data=go.Box(
            x=df["score"],
            y=df["team"],
            orientation="h",
            boxpoints="all",
            jitter=0.4,
            pointpos=0,
            fillcolor="rgba(0,0,0,0)",
            line=dict(color="rgba(0,0,0,0)"),
            marker=dict(size=10, opacity=0.8, color="#2a9d8f"),
            customdata=df[["sample_id", "shift", "region", "passed"]],
            hovertemplate=(
                "sample_id=%{customdata[0]}<br>"
                "team=%{y}<br>"
                "score=%{x}<br>"
                "shift=%{customdata[1]}<br>"
                "region=%{customdata[2]}<br>"
                "passed=%{customdata[3]}<extra></extra>"
            ),
            name="score",
        )
    )
    fig_horizontal.update_layout(
        title="Score by Team (horizontal) — same data, transposed",
        xaxis_title="Score",
        yaxis_title="Team",
        dragmode="select",
        showlegend=False,
    )

    strip_horizontal = mo.ui.plotly(fig_horizontal)
    strip_horizontal
    return (strip_horizontal,)


@app.cell
def _(df, mo, selected_rows, strip_horizontal):
    _sel_h = selected_rows(strip_horizontal.value, df)

    _summary_h = (
        f"{len(_sel_h)} rows — avg score: {_sel_h['score'].mean():.1f}"
        if not _sel_h.empty
        else "No rows selected yet."
    )

    mo.md(f"""
    ### Horizontal Selection

    **{_summary_h}**

    **Indices:** {strip_horizontal.indices}
    """)
    return


@app.cell
def _(df, mo, selected_rows, strip_horizontal):
    mo.ui.table(selected_rows(strip_horizontal.value, df))
    return


if __name__ == "__main__":
    app.run()
