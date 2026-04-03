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
    # Reactive Plotly Box Plot Selection

    This example demonstrates reactive box plot selections with `mo.ui.plotly`.

    Try:
    - **Drag a box** over jittered sample points to select them
    - **Click** a box element (median line, whisker, or box body) to select the
      entire group
    - Watch the table and stats below update from your selection

    The `customdata` field embeds the original row ID (`sample_id`) so selected
    points map back to the source DataFrame without relying on raw indices.
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
        # Box-body clicks embed sample_id as customdata[0], not a top-level key.
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
def _(df, go, mo):
    mo.md("## Single-Trace Box Plot")

    fig_single = go.Figure(
        data=go.Box(
            x=df["team"],
            y=df["score"],
            customdata=df[["sample_id", "shift", "region", "passed"]],
            boxpoints="all",
            jitter=0.35,
            pointpos=0,
            marker=dict(size=10, opacity=0.8, color="#1f77b4"),
            line=dict(color="#1f77b4"),
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
        title="Score by Team — drag over points or click a box",
        xaxis_title="Team",
        yaxis_title="Score",
        dragmode="select",
    )

    box_single = mo.ui.plotly(fig_single)
    box_single
    return (box_single,)


@app.cell
def _(box_single, df, mo, selected_rows):
    _sel = selected_rows(box_single.value, df)

    _summary = (
        f"{len(_sel)} rows selected — "
        f"avg score: {_sel['score'].mean():.1f} — "
        f"pass rate: {_sel['passed'].mean():.0%}"
        if not _sel.empty
        else "No rows selected yet."
    )

    mo.md(f"""
    ### Single-Trace Selection

    **{_summary}**

    **Indices:** {box_single.indices}
    """)
    return


@app.cell
def _(box_single, df, mo, selected_rows):
    mo.ui.table(selected_rows(box_single.value, df))
    return


@app.cell
def _(df, mo, px):
    mo.md("## Grouped Box Plot")

    fig_grouped = px.box(
        df,
        x="team",
        y="score",
        color="shift",
        points="all",
        custom_data=["sample_id", "shift", "region", "passed"],
        title="Score by Team and Shift — drag to compare groups",
    )
    fig_grouped.update_traces(
        jitter=0.35,
        pointpos=0,
        hovertemplate=(
            "sample_id=%{customdata[0]}<br>"
            "team=%{x}<br>"
            "score=%{y}<br>"
            "shift=%{customdata[1]}<br>"
            "region=%{customdata[2]}<br>"
            "passed=%{customdata[3]}<extra></extra>"
        ),
    )
    fig_grouped.update_layout(dragmode="select", xaxis_title="Team", yaxis_title="Score")

    box_grouped = mo.ui.plotly(fig_grouped)
    box_grouped
    return (box_grouped,)


@app.cell
def _(box_grouped, df, mo, selected_rows):
    _sel_g = selected_rows(box_grouped.value, df)

    _summary_g = (
        f"{len(_sel_g)} rows — "
        + ", ".join(
            f"{team}: {count}"
            for team, count in _sel_g.groupby("team").size().items()
        )
        if not _sel_g.empty
        else "No rows selected yet."
    )

    mo.md(f"""
    ### Grouped Selection

    **{_summary_g}**

    **Indices:** {box_grouped.indices}

    **Range:** {box_grouped.ranges}
    """)
    return


@app.cell
def _(box_grouped, df, mo, selected_rows):
    mo.ui.table(selected_rows(box_grouped.value, df))
    return


@app.cell
def _(df, go, mo):
    mo.md("## Horizontal Box Plot")

    fig_horizontal = go.Figure(
        data=go.Box(
            x=df["score"],
            y=df["team"],
            orientation="h",
            customdata=df[["sample_id", "shift", "region", "passed"]],
            boxpoints="all",
            jitter=0.35,
            pointpos=0,
            marker=dict(size=10, opacity=0.8, color="#2a9d8f"),
            line=dict(color="#2a9d8f"),
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
    )

    box_horizontal = mo.ui.plotly(fig_horizontal)
    box_horizontal
    return (box_horizontal,)


@app.cell
def _(box_horizontal, df, mo, selected_rows):
    _sel_h = selected_rows(box_horizontal.value, df)

    _summary_h = (
        f"{len(_sel_h)} rows — avg score: {_sel_h['score'].mean():.1f}"
        if not _sel_h.empty
        else "No rows selected yet."
    )

    mo.md(f"""
    ### Horizontal Selection

    **{_summary_h}**

    **Indices:** {box_horizontal.indices}
    """)
    return


@app.cell
def _(box_horizontal, df, mo, selected_rows):
    mo.ui.table(selected_rows(box_horizontal.value, df))
    return


if __name__ == "__main__":
    app.run()
