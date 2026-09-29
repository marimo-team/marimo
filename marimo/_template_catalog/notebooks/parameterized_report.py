# Copyright 2026 Marimo. All rights reserved.
import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    project = mo.ui.text(label="Project", value="Autumn launch")
    progress = mo.ui.slider(
        start=0,
        stop=100,
        step=5,
        value=65,
        label="Progress",
    )
    status = mo.ui.dropdown(
        options=["On track", "At risk", "Blocked"],
        value="On track",
        label="Status",
    )
    mo.hstack([project, progress, status], widths="equal")
    return progress, project, status


@app.cell
def _(mo, progress, project, status):
    remaining = 100 - progress.value
    mo.md(f"""
    # {project.value}: status report

    | Metric | Value |
    | --- | --- |
    | Status | **{status.value}** |
    | Completed | {progress.value}% |
    | Remaining | {remaining}% |

    ## Summary

    {project.value} is **{status.value.lower()}** with
    **{progress.value}%** of the planned work complete.
    """)
    return


if __name__ == "__main__":
    app.run()
