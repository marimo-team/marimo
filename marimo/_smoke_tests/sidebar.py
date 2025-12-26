# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="full")


@app.cell
def _(mo):
    mo.sidebar(
        [
            mo.md("# marimo"),
            mo.nav_menu(
                {
                    "#home": f"{mo.icon('lucide:home')} Home",
                    "#about": f"{mo.icon('lucide:user')} About",
                    "#contact": f"{mo.icon('lucide:phone')} Contact",
                    "Links": {
                        "https://twitter.com/marimo_io": "Twitter",
                        "https://github.com/marimo-team/marimo": "GitHub",
                    },
                },
                orientation="vertical",
            ),
        ],
        footer=[
            mo.md(
                """

        ### Footer

        - [Twitter](https://twitter.com/marimo_io)
        - [GitHub](https://github.com/marimo-team/marimo)
        """
            )
        ],
        width="500px",
    )
    return


@app.cell
def _(mo):
    [
        mo.ui.button(
            label=f"{mo.icon('lucide:home')} Home",
        ),
        mo.ui.button(
            label=f"{mo.icon('lucide:home')} Home {mo.icon('lucide:external-link')}",
        ),
    ]
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.nav_menu(
        {
            "#home": f"{mo.icon('lucide:home')} Home",
            "#about": f"{mo.icon('lucide:user')} About",
            "#contact": f"{mo.icon('lucide:phone')} Contact",
        },
        orientation="vertical",
    )
    return


@app.cell
def _(mo):
    mo.nav_menu(
        {
            "#home": f"{mo.icon('lucide:home')} Home",
            "#about": f"{mo.icon('lucide:user')} About",
            "#contact": f"{mo.icon('lucide:phone')} Contact",
        }
    )
    return


if __name__ == "__main__":
    app.run()
