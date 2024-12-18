# Routes

::: marimo.routes
python
import marimo

app = marimo.App()

@app.cell
def __():
   import marimo as mo
   return


@app.cell
def __():
    mo.sidebar(
        [
            mo.md("# marimo"),
            mo.nav_menu(
                {
                    "#/": f"{mo.icon('lucide:home')} Home",
                    "#/about": f"{mo.icon('lucide:user')} About",
                    "#/contact": f"{mo.icon('lucide:phone')} Contact",
                    "Links": {
                        "https://twitter.com/marimo_io": "Twitter",
                        "https://github.com/marimo-team/marimo": "GitHub",
                    },
                },
                orientation="vertical",
            ),
        ]
    )
    return

@app.cell
def __():
    mo.routes({
        "#/": mo.md("# Home"),
        "#/about": mo.md("# About"),
        "#/contact": mo.md("# Contact"),
        mo.routes.CATCH_ALL: mo.md("# Home"),
    })
    return
