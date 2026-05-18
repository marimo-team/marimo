# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.23.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Label alignment smoke test

    Visually verify that labels render at the correct position relative to
    their controls across every `Labeled` configuration. See the comments
    in each cell for the expected vs. regression behavior.

    Related: PR #9100 (table label padding) and the switch/checkbox
    vertical-centering regression introduced by it.
    """)
    return


@app.cell
def _(mo):
    # Case 1 — Inline label, side alignment (the original regression).
    # Expected: each label's text is vertically centered with its control
    # (switch knob, checkbox box, radio dot all line up with the cap-height of
    # the label text).
    # Regression: label text appears below the control's vertical center.
    mo.vstack(
        [
            mo.md("### Case 1 — inline (side) labels"),
            mo.ui.switch(label="Switch"),
            mo.ui.checkbox(label="Checkbox"),
            mo.ui.radio(["A", "B", "C"], label="Inline radio", inline=True),
        ]
    )
    return


@app.cell
def _(mo):
    # Case 2 — Side labels with markdown content.
    # Expected: bold/italic/code render inline with the control, still
    # vertically centered.
    mo.vstack(
        [
            mo.md("### Case 2 — inline labels with markdown"),
            mo.ui.switch(label="**Bold** label"),
            mo.ui.checkbox(label="*Italic* label"),
            mo.ui.switch(label="Label with `code`"),
        ]
    )
    return


@app.cell
def _(mo):
    # Case 3 — Side labels that are long enough to wrap.
    # Expected: control sits centered against the multi-line label block; the
    # gap between label and control stays consistent.
    mo.vstack(
        [
            mo.md("### Case 3 — long inline labels"),
            mo.ui.switch(
                label=(
                    "A fairly long switch label that should still align "
                    "with the switch even when it wraps to multiple lines"
                )
            ),
            mo.ui.checkbox(
                label=(
                    "A fairly long checkbox label that should still align "
                    "with the checkbox even when it wraps to multiple lines"
                )
            ),
        ]
    )
    return


@app.cell
def _(mo):
    # Case 4 — Top labels (no full_width).
    # Expected: label sits flush left above each control with a small gap.
    mo.vstack(
        [
            mo.md("### Case 4 — top labels"),
            mo.ui.text(label="Text input"),
            mo.ui.number(0, 10, label="Number input"),
            mo.ui.dropdown(["A", "B", "C"], label="Dropdown"),
            mo.ui.radio(["A", "B", "C"], label="Stacked radio"),
            mo.ui.date(label="Date"),
        ]
    )
    return


@app.cell
def _(mo):
    # Case 5 — Top labels with full_width.
    # Expected: label flush-left above the full-width control; control spans
    # the cell width.
    mo.vstack(
        [
            mo.md("### Case 5 — full-width top labels"),
            mo.ui.text(label="Full width text", full_width=True),
            mo.ui.text_area(label="Full width text area", full_width=True),
            mo.ui.dropdown(
                ["A", "B", "C"], label="Full width dropdown", full_width=True
            ),
            mo.ui.multiselect(
                ["A", "B", "C"], label="Full width multiselect", full_width=True
            ),
        ]
    )
    return


@app.cell
def _(mo):
    # Case 6 — Markdown headings as labels.
    # Expected: the heading renders at full size; flush-left.
    mo.vstack(
        [
            mo.md("### Case 6 — markdown headings as labels"),
            mo.ui.text(label="# H1 label", full_width=True),
            mo.ui.text(label="## H2 label", full_width=True),
            mo.ui.text(label="### H3 label", full_width=True),
        ]
    )
    return


@app.cell
def _(mo):
    # Case 7 — Table labels (PR #9100 case).
    # Expected: the label aligns with the table's first-column cell content
    # (i.e. it inherits `--marimo-table-edge-padding` because the cell output
    # is a single flush table). This is what the wrapper `<div part="label">`
    # exists for.
    mo.ui.table(
        data=[
            {"Name": "Alice", "Score": 95, "Grade": "A"},
            {"Name": "Bob", "Score": 82, "Grade": "B"},
        ],
        label="Table",
    )
    return


@app.cell
def _(mo):
    # Case 8 — Table with a markdown heading label (PR #9100's "Cars dataset"
    # case).
    # Expected: the heading renders at h1 size and aligns with the table's
    # first-column content edge.
    mo.ui.table(
        data=[
            {"Name": "Alice", "Score": 95, "Grade": "A"},
            {"Name": "Bob", "Score": 82, "Grade": "B"},
        ],
        label="# Heading label",
    )
    return


@app.cell
def _(mo):
    # Case 9 — Table inside a vstack (NOT flush with the cell output).
    # Expected: no edge padding is applied; label flush-left at 0.
    mo.vstack(
        [
            mo.md("### Case 9 — table inside a container (not flush)"),
            mo.ui.table(
                data=[
                    {"Name": "Alice", "Score": 95, "Grade": "A"},
                    {"Name": "Bob", "Score": 82, "Grade": "B"},
                ],
                label="Non-flush table label",
            ),
        ]
    )
    return


@app.cell
def _(mo):
    # Case 10 — Code editor (uses align="top" fullWidth=true).
    # Expected: label flush-left above the editor; editor spans full width.
    mo.ui.code_editor(value="print('hello')", label="Code editor")
    return


@app.cell
def _(mo):
    # Case 11 — Stack of side-labeled controls in an hstack.
    # Expected: each switch/checkbox text remains centered with its control;
    # they don't visually drift relative to one another.
    mo.hstack(
        [
            mo.ui.switch(label="One"),
            mo.ui.switch(label="Two"),
            mo.ui.checkbox(label="Three"),
            mo.ui.checkbox(label="Four"),
        ],
        justify="start",
    )
    return


@app.cell
def _(mo):
    # Case 12 — Empty / no label sanity check.
    # Expected: control renders without any leading whitespace or vertical
    # offset; layout matches an explicitly labeled control's control area.
    mo.vstack(
        [
            mo.md("### Case 12 — no labels"),
            mo.ui.switch(),
            mo.ui.checkbox(),
            mo.ui.text(),
            mo.ui.dropdown(["A", "B", "C"]),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
