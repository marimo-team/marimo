import marimo

__generated_with = "0.18.2"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    orientation = mo.ui.dropdown(["vertical", "horizontal"], value="horizontal")
    orientation
    return (orientation,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Nav Menu Submenu Positioning Test (Issue #7398)

    **Expected behavior:** Submenus should position themselves intelligently
    relative to their parent menu item, especially when the parent is on the
    right side of the menu.
    """)
    return


@app.cell
def _(mo, orientation):
    # Reproduce the exact example from the issue
    mo.nav_menu(
        menu={
            "Menu Item 1": {"/": "Subitem 1"},
            "Menu Item 2": {"/": "Subitem 2"},
            "Menu Item 3": {"/": "Subitem 3"},
            "Menu Item 4": {"/": "Subitem 4"},
            "Menu Item 5": {"/": "Subitem 5"},
            "Menu Item 6": {"/": "Subitem 6"},
            "Menu Item 7": {"/": "Subitem 7"},
        },
        orientation=orientation.value,
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ---
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## More Complex Example

    This example shows multiple submenu items to better demonstrate the issue.
    Try hovering over items on the right side.
    """)
    return


@app.cell
def _(mo, orientation):
    mo.nav_menu(
        {
            "Item 1": {
                "#item1-sub1": "Subitem 1.1",
                "#item1-sub2": "Subitem 1.2",
                "#item1-sub3": "Subitem 1.3",
            },
            "Item 2": {
                "#item2-sub1": "Subitem 2.1",
                "#item2-sub2": "Subitem 2.2",
            },
            "Item 3": {
                "#item3-sub1": "Subitem 3.1",
                "#item3-sub2": "Subitem 3.2",
            },
            "Item 4": {
                "#item4-sub1": "Subitem 4.1",
                "#item4-sub2": "Subitem 4.2",
            },
            "Item 5": {
                "#item5-sub1": "Subitem 5.1",
                "#item5-sub2": "Subitem 5.2",
            },
            "Item 6": {
                "#item6-sub1": "Subitem 6.1",
                "#item6-sub2": "Subitem 6.2",
                "#item6-sub3": {
                    "label": "Subitem 6.3",
                    "description": "This submenu is especially hard to reach!",
                },
            },
            "Item 7": {
                "#item7-sub1": "Subitem 7.1",
                "#item7-sub2": "Subitem 7.2",
                "#item7-sub3": {
                    "label": "Subitem 7.3",
                    "description": "Nearly impossible to access this one",
                },
            },
        },
        orientation=orientation.value,
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ---
    """)
    return


if __name__ == "__main__":
    app.run()
