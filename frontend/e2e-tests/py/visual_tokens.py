# /// script
# [tool.marimo.runtime]
# auto_instantiate = true
# ///
import marimo

__generated_with = "0.24.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    focused_input = mo.ui.text(
        value="Semantic input",
        label="Focused input",
    )

    controls = mo.hstack(
        [
            focused_input,
            mo.ui.checkbox(value=True, label="Checkbox"),
            mo.ui.dropdown(
                options=["Alpha", "Beta"],
                value="Alpha",
                label="Dropdown",
            ),
        ],
        justify="start",
        wrap=True,
        gap=1,
    )

    buttons = mo.hstack(
        [
            mo.ui.button(label="Neutral", kind="neutral"),
            mo.ui.button(label="Success", kind="success"),
            mo.ui.button(label="Warning", kind="warn"),
            mo.ui.button(label="Danger", kind="danger"),
        ],
        justify="start",
        wrap=True,
        gap=1,
    )

    callouts = mo.hstack(
        [
            mo.md("Neutral state").callout(kind="neutral", title="Neutral"),
            mo.md("Information state").callout(kind="info", title="Info"),
            mo.md("Success state").callout(kind="success", title="Success"),
            mo.md("Warning state").callout(kind="warn", title="Warning"),
            mo.md("Danger state").callout(kind="danger", title="Danger"),
        ],
        justify="start",
        wrap=True,
        gap=0.5,
    )

    mo.vstack(
        [
            mo.md(
                "# Semantic token fixture\n"
                "Body text with a [link](#) and `inline code`."
            ),
            controls,
            buttons,
            callouts,
        ],
        gap=1,
    )
    return (focused_input,)


if __name__ == "__main__":
    app.run()
