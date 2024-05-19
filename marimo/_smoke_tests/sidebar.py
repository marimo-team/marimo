# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.5.2"
app = marimo.App()


@app.cell
def __(mo):
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
    )
    return


@app.cell
def __(mo):
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
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
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
def __(mo):
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
