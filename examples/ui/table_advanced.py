# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Tables

    > “Sometimes I’ll start a sentence and I don’t even know where it’s going. I just hope I find it along the way.”
    — Michael Scott
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    _Create rich tables with selectable rows using_ `mo.ui.table`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    **Single selection.**
    """)
    return


@app.cell
def _(mo, office_characters):
    single_select_table = mo.ui.table(
        office_characters,
        selection="single",
        pagination=True,
    )
    return (single_select_table,)


@app.cell
def _(mo, single_select_table):
    mo.ui.tabs({"table": single_select_table, "selection": single_select_table.value})
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    **Multi-selection.**
    """)
    return


@app.cell
def _(mo, office_characters):
    multi_select_table = mo.ui.table(
        office_characters,
        selection="multi",
        pagination=True,
    )
    return (multi_select_table,)


@app.cell
def _(mo, multi_select_table):
    mo.ui.tabs({"table": multi_select_table, "selection": multi_select_table.value})
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    **No selection.**
    """)
    return


@app.cell
def _(mo, office_characters):
    table = mo.ui.table(
        office_characters,
        label="Employees",
        selection=None,
    )

    table
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    **Select individual cells**
    """)
    return


@app.cell
def _(mo):
    data = {str(col): [col * 10 + row for row in range(10)] for col in range(10)}
    mo.ui.table(data, selection="multi-cell", initial_selection=[("3", "5"),("9","8")])
    return


@app.cell
def _(mo):
    mo.md("""
    **Style individual cells**
    """)
    return


@app.cell
def _(mo):
    def apply_styling(row_id, column_name, value):
        row = int(row_id)
        column = int(column_name)
        r = row / 8 * 12
        g = column / 2 * 32
        b = (row + column) / 10 * 16
        return {
            "backgroundColor": f"rgb({r % 256}, {g % 256}, {b % 256})",
            "color": "white"
            if (r * 0.299 + g * 0.587 + b * 0.114) < 186
            else "black",
        }


    colors = {
        str(col): [row * 20 + col  for row in range(320)] for col in range(10)
    }
    color_table = mo.ui.table(
        data=colors, pagination=True, page_size=16, style_cell=apply_styling
    )
    color_table
    return


@app.cell
def _(mo):
    office_characters = [
        {
            "first_name": "Michael",
            "last_name": "Scott",
            "skill": mo.ui.slider(1, 10, value=3),
            "favorite place": mo.image(src="https://picsum.photos/100", rounded=True),
        },
        {
            "first_name": "Jim",
            "last_name": "Halpert",
            "skill": mo.ui.slider(1, 10, value=7),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Pam",
            "last_name": "Beesly",
            "skill": mo.ui.slider(1, 10, value=3),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Dwight",
            "last_name": "Schrute",
            "skill": mo.ui.slider(1, 10, value=7),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Angela",
            "last_name": "Martin",
            "skill": mo.ui.slider(1, 10, value=5),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Kevin",
            "last_name": "Malone",
            "skill": mo.ui.slider(1, 10, value=3),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Oscar",
            "last_name": "Martinez",
            "skill": mo.ui.slider(1, 10, value=3),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Stanley",
            "last_name": "Hudson",
            "skill": mo.ui.slider(1, 10, value=5),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Phyllis",
            "last_name": "Vance",
            "skill": mo.ui.slider(1, 10, value=5),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Meredith",
            "last_name": "Palmer",
            "skill": mo.ui.slider(1, 10, value=7),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Creed",
            "last_name": "Bratton",
            "skill": mo.ui.slider(1, 10, value=3),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Ryan",
            "last_name": "Howard",
            "skill": mo.ui.slider(1, 10, value=5),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Kelly",
            "last_name": "Kapoor",
            "skill": mo.ui.slider(1, 10, value=3),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Toby",
            "last_name": "Flenderson",
            "skill": mo.ui.slider(1, 10, value=3),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Darryl",
            "last_name": "Philbin",
            "skill": mo.ui.slider(1, 10, value=7),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Erin",
            "last_name": "Hannon",
            "skill": mo.ui.slider(1, 10, value=5),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Andy",
            "last_name": "Bernard",
            "skill": mo.ui.slider(1, 10, value=5),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Jan",
            "last_name": "Levinson",
            "skill": mo.ui.slider(1, 10, value=5),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "David",
            "last_name": "Wallace",
            "skill": mo.ui.slider(1, 10, value=3),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
        {
            "first_name": "Holly",
            "last_name": "Flax",
            "skill": mo.ui.slider(1, 10, value=7),
            "favorite place": mo.image(src="https://picsum.photos/100"),
        },
    ]
    return (office_characters,)


if __name__ == "__main__":
    app.run()
