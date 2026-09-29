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
    entry_form = (
        mo.md("""
        # New project request

        {name}

        {priority}

        {estimate}

        {notes}
        """)
        .batch(
            name=mo.ui.text(label="Project name", value="Website refresh"),
            priority=mo.ui.dropdown(
                options=["Low", "Medium", "High"],
                value="Medium",
                label="Priority",
            ),
            estimate=mo.ui.number(
                start=1,
                value=5,
                label="Estimated days",
            ),
            notes=mo.ui.text_area(
                label="Notes",
                value="Update the landing page and navigation.",
            ),
        )
        .form(submit_button_label="Add request", clear_on_submit=False)
    )
    entry_form
    return (entry_form,)


@app.cell
def _(entry_form, mo):
    submitted_entry = entry_form.value or {
        "name": "Website refresh",
        "priority": "Medium",
        "estimate": 5,
        "notes": "Update the landing page and navigation.",
    }
    mo.vstack(
        [
            mo.md("## Submitted request"),
            mo.ui.table([submitted_entry], selection=None),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
