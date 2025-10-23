import marimo

__generated_with = "0.17.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Issue #6894""")
    return


@app.cell
def _():
    import marimo as mo


    def box(text):
        return mo.md(
            f"""
            {text}:
            ```
            {text}
            ```
            """
        )


    mo.vstack(
        [
            box("Box A: Copying from this box works"),
            mo.accordion(
                {
                    "Accordibox": mo.vstack(
                        [box("Box B: Copying from this box doesn't work")]
                    )
                },
                lazy=True,
            ),
        ]
    )
    return (mo,)


if __name__ == "__main__":
    app.run()
