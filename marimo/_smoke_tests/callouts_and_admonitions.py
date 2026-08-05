import marimo

__generated_with = "0.23.15"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""
    # Markdown admonitions

    /// note | "Note"
    This is a `note` admonition, written in markdown.
    ///

    /// warning | "Warning"
    This is a `warning` admonition.
    ///

    /// danger | "Danger"
    This is a `danger` admonition.
    ///

    /// tip | "Tip"
    This is a `tip` admonition.
    ///
    """)
    return


@app.cell
def _(mo):
    mo.vstack(
        [
            mo.md("# Callouts"),
            mo.callout(mo.md("A `neutral` callout, no title."), kind="neutral"),
            mo.callout(
                mo.md("An `info` callout with a title."),
                kind="info",
                title="Info"
            ),
            mo.callout(
                mo.md("A `warn` callout with a title."),
                kind="warn",
                title="Warning"
            ),
            mo.callout(
                mo.md("A `danger` callout with a title."),
                kind="danger",
                title="Danger"
            ),
            mo.callout(
                mo.md("A `success` callout with a title."),
                kind="success",
                title="Success"
            ),
            mo.md("The fluent API works too:"),
            mo.md("Hooray, you did it!").callout(kind="success")
        ]
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    # Stress tests: rich content in callouts
    """)
    return


@app.cell
def _():
    import matplotlib.pyplot as plt
    import numpy as np
    import polars as pl

    return np, pl, plt


@app.cell
def _(mo, np, plt):
    fig, ax = plt.subplots(figsize=(6, 3))
    xs = np.linspace(0, 2 * np.pi, 200)
    ax.plot(xs, np.sin(xs))
    ax.set_title("sin(x)")
    mo.callout(ax, kind="info", title="A matplotlib plot")
    return


@app.cell
def _(mo):
    stress_slider = mo.ui.slider(0, 100, value=50, label="Amplitude")
    stress_dropdown = mo.ui.dropdown(
        options=["sin", "cos", "tan"], value="sin", label="Function"
    )
    stress_text = mo.ui.text(placeholder="Type something...", label="Notes")
    stress_button = mo.ui.run_button(label="Run")
    mo.callout(
        mo.vstack(
            [
                mo.hstack([stress_slider, stress_dropdown], justify="start"),
                stress_text,
                stress_button,
            ]
        ),
        kind="warn",
        title="Interactive UI elements",
    )
    return stress_dropdown, stress_slider, stress_text


@app.cell
def _(mo, stress_dropdown, stress_slider, stress_text):
    mo.callout(
        mo.md(
            f"Slider: `{stress_slider.value}`, dropdown: "
            f"`{stress_dropdown.value}`, text: `{stress_text.value!r}`"
        ),
        kind="success",
        title="Values react across cells",
    )
    return


@app.cell
def _(mo, np, pl):
    df = pl.DataFrame(
        {
            "x": np.arange(10),
            "sin(x)": np.sin(np.arange(10)),
            "label": [f"row {i}" for i in range(10)],
        }
    )
    mo.callout(df, kind="neutral", title="A polars DataFrame")
    return (df,)


@app.cell
def _(df, mo):
    stress_table = mo.ui.table(df, selection="multi", page_size=5)
    mo.callout(stress_table, kind="info", title="A selectable mo.ui.table")
    return


@app.cell
def _(mo):
    mo.callout(
        mo.callout(
            mo.md(
                r"""
                A callout inside a callout, holding LaTeX
                ($e^{i\pi} + 1 = 0$), a markdown admonition:

                /// warning | Nested admonition
                Markdown admonitions render inside callouts too.
                ///

                and a code block:

                ```python
                def fib(n: int) -> int:
                    return n if n < 2 else fib(n - 1) + fib(n - 2)
                ```
                """
            ),
            kind="danger",
            title="Inner callout",
        ),
        kind="neutral",
        title="Outer callout",
    )
    return


@app.cell
def _(mo):
    mo.callout(
        mo.vstack(
            [
                mo.hstack(
                    [
                        mo.stat(value="42", label="Answer", caption="+3.2%"),
                        mo.stat(value="1.7s", label="Runtime"),
                    ],
                    justify="start",
                ),
                mo.accordion(
                    {"Details": mo.md("An accordion inside a callout.")}
                ),
                mo.ui.tabs(
                    {
                        "Tab A": mo.md("First tab"),
                        "Tab B": mo.md("Second tab"),
                    }
                ),
            ]
        ),
        kind="info",
        title="Stats, accordions, and tabs",
    )
    return


@app.cell
def _(mo):
    mo.callout(
        mo.md("Edge cases: does the title escape `<b>HTML</b>` and emoji?"),
        kind="warn",
        title=(
            "A very long title with <b>HTML tags</b> & ampersands 🎉 that "
            "should be escaped, not rendered, and should wrap gracefully "
            "when it exceeds the width of the callout container"
        ),
    )
    return


if __name__ == "__main__":
    app.run()
