# Sidebar

/// marimo-embed
    size: medium

```python
@app.cell
def __():
    mo.sidebar(
        [
            mo.md("# marimo"),
            mo.nav_menu(
                {
                    "#/home": f"{mo.icon('lucide:home')} Home",
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
```

///

::: marimo.sidebar
