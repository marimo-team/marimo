# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
#     "plotly==6.5.1",
# ]
# ///

import marimo

__generated_with = "0.20.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import plotly.graph_objects as go

    return go, mo


@app.cell
def _(mo):
    mo.md("""
    # Reactive Plotly Pure Line Selection

    This example focuses on pure line traces (`mode="lines"`).

    Try:
    - clicking a line point
    - box selection
    - lasso selection

    Then inspect `value`, `indices`, and `ranges` in Python.
    """)
    return


@app.cell
def _(go, mo):
    mo.md("## Single Pure Line")

    _fig_single = go.Figure(
        data=go.Scatter(
            x=[0, 1, 2, 3, 4, 5, 6],
            y=[0, 4, 2, 6, 3, 8, 5],
            mode="lines",
            name="line_a",
            line={"color": "#636EFA", "width": 2},
        )
    )
    _fig_single.update_layout(
        title="Click + Box/Lasso on Pure Line",
        xaxis_title="x",
        yaxis_title="y",
        clickmode="event+select",
    )

    pure_line = mo.ui.plotly(_fig_single)
    pure_line
    return (pure_line,)


@app.cell
def _(mo, pure_line):
    mo.md(f"""
    ### Single Line Selection Output

    **Selected rows:** {len(pure_line.value)}

    **Selected indices:** {pure_line.indices}

    **Selection ranges:** {pure_line.ranges}

    **Preview:**
    {pure_line.value[:10]}
    """)
    return


@app.cell
def _(go, mo):
    mo.md("## Multiple Pure Lines")

    _fig_multi = go.Figure()
    _fig_multi.add_trace(
        go.Scatter(
            x=[1, 2, 3, 4, 5],
            y=[12, 15, 18, 14, 16],
            mode="lines",
            name="inside_box_line",
            line={"color": "#00CC96", "width": 2},
        )
    )
    _fig_multi.add_trace(
        go.Scatter(
            x=[1, 2, 3, 4, 5],
            y=[50, 60, 70, 65, 55],
            mode="lines",
            name="outside_box_line",
            line={"color": "#EF553B", "width": 2},
        )
    )
    _fig_multi.update_layout(
        title="XY Filtering Across Multiple Pure Lines",
        xaxis_title="x",
        yaxis_title="y",
        clickmode="event+select",
    )

    multi_line = mo.ui.plotly(_fig_multi)
    multi_line
    return (multi_line,)


@app.cell
def _(mo, multi_line):
    mo.md(f"""
    ### Multi-Line Selection Output

    **Selected rows:** {len(multi_line.value)}

    **Selected indices:** {multi_line.indices}

    **Selection ranges:** {multi_line.ranges}

    **Preview:**
    {multi_line.value[:10]}
    """)
    return


if __name__ == "__main__":
    app.run()
