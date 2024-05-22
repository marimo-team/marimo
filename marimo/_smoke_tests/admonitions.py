# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.0"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    kinds = [
        # ---
        "info",
        "note",
        # ---
        "danger",
        "error",
        "caution",
        # ---
        "hint",
        # ---
        "important",
        # ---
        "tip",
        # ---
        "attention",
        "warning",
    ]

    def create(kind):
        return mo.md(
        rf"""

            !!! {kind} "{kind} admonition"
                This is an admonition for {kind}
            """
        )

    mo.vstack([create(kind) for kind in kinds])
    return create, kinds


@app.cell
def __(mo):
    mo.md("# Misc")
    return


@app.cell
def __(mo):
    mo.md(
        rf"""
        !!! important ""
            This is an admonition box without a title.
        """
    )
    return


if __name__ == "__main__":
    app.run()
