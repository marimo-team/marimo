import marimo

__generated_with = "0.0.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    # A horizontal nav menu with a nested group. The group's dropdown is
    # portaled out of the cell's overflow container; this exercises the
    # clipping/positioning fix in NavigationMenuPlugin.
    mo.nav_menu(
        {
            "#section1": "Section 1",
            "#section2": "Section 2",
            "Links": {
                "https://marimo.io": "marimo.io",
                "https://github.com/marimo-team/marimo": {
                    "label": "GitHub",
                    "description": "GitHub repository",
                },
            },
        },
        orientation="horizontal",
    )
    return


if __name__ == "__main__":
    app.run()
