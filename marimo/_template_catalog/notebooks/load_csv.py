# Copyright 2026 Marimo. All rights reserved.
import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import csv
    import io

    import marimo as mo

    return csv, io, mo


@app.cell
def _(mo):
    sample_csv = """region,product,units,revenue
Americas,Notebook,12,228
Asia,Notebook,18,333
Europe,Pen set,9,108
Oceania,Desk pad,15,360
Africa,Pen set,7,81
"""
    uploaded_file = mo.ui.file(
        filetypes=[".csv"],
        kind="area",
        label="Upload a CSV",
    )
    mo.vstack(
        [
            mo.md("# Explore a CSV\n\nUpload your own file or use the sample."),
            uploaded_file,
        ]
    )
    return sample_csv, uploaded_file


@app.cell
def _(csv, io, sample_csv, uploaded_file):
    source_name = uploaded_file.name() or "sample_sales.csv"
    csv_text = (
        uploaded_file.contents().decode()
        if uploaded_file.name()
        else sample_csv
    )
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    return rows, source_name


@app.cell
def _(mo, rows, source_name):
    mo.vstack(
        [
            mo.md(f"**{source_name}** · {len(rows)} rows"),
            mo.ui.table(rows, selection=None),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
