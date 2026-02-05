# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Inputs

    There are many way that a user can input with your notebook, such as text boxes, sliders, dates, and more.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Text boxes
    """)
    return


@app.cell
def _(mo):
    mo.hstack(
        [
            username := mo.ui.text(label="Username"),
            email := mo.ui.text(label="Email", kind="email"),
            mo.ui.text(label="Password", kind="password"),
        ]
    )
    return (username,)


@app.cell
def _(mo, username):
    mo.stop(not username.value, mo.md("What is your name?"))

    mo.md(f"👋 Hello {username.value}, nice to meet you!")
    return


@app.cell
def _(mo):
    mo.ui.text_area(
        label="A space for your thoughts", full_width=True, max_length=1000
    )
    return


@app.cell
def _(mo):
    mo.ui.number(label="What is your favorite number?", start=0, stop=10)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Sliders
    """)
    return


@app.cell
def _(mo):
    slider = mo.ui.slider(0, 100, value=50, label="Basic slider", show_value=True)
    range_slider = mo.ui.range_slider(
        0, 100, value=(30, 70), label="Range slider", show_value=True
    )
    custom_steps = mo.ui.slider(
        steps=[1, 10, 100, 1000], value=10, label="Custom steps", show_value=True
    )
    vertical = mo.ui.slider(
        0, 100, value=50, label="Vertical slider", orientation="vertical"
    )
    mo.vstack([slider, range_slider, custom_steps, vertical]).center()
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Checkboxes and Radios
    """)
    return


@app.cell
def _(mo):
    COLORS = ["red", "green", "blue"]
    colors = mo.ui.array(
        [mo.ui.checkbox(label=color) for color in COLORS],
    )

    shape = mo.ui.radio(
        ["circle", "square", "triangle"], inline=True, value="square"
    )
    mo.md(f"""
    Let's build something:

    **Pick a shape:**

    {shape}

    **Pick a color:**

    {colors.hstack().left()}
    """).center()
    return COLORS, colors, shape


@app.cell(hide_code=True)
def _(COLORS, colors, mo, shape):
    selected_colors = [color for i, color in enumerate(COLORS) if colors.value[i]]


    def draw_shape(shape, colors):
        if not colors:
            return ""

        gradient = ""
        if isinstance(colors, list) and len(colors) > 1:
            gradient_id = f"grad{hash(tuple(colors)) % 1000}"
            stops = "".join(
                [
                    f'<stop offset="{i/(len(colors)-1)}" style="stop-color:{color};" />'
                    for i, color in enumerate(colors)
                ]
            )
            gradient = f'<defs><linearGradient id="{gradient_id}" x1="0%" y1="0%" x2="100%" y2="100%">{stops}</linearGradient></defs>'
            fill_color = f"url(#{gradient_id})"
        else:
            fill_color = colors if isinstance(colors, str) else colors[0]

        if shape == "circle":
            html = f'<svg width="100" height="100">{gradient}<circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="{fill_color}" /></svg>'
        elif shape == "square":
            html = f'<svg width="100" height="100">{gradient}<rect width="80" height="80" x="10" y="10" stroke="black" stroke-width="3" fill="{fill_color}" /></svg>'
        elif shape == "triangle":
            html = f'<svg width="100" height="100">{gradient}<polygon points="50,10 90,90 10,90" stroke="black" stroke-width="3" fill="{fill_color}" /></svg>'
        else:
            html = "Shape not recognized"
        return mo.Html(html)


    mo.md(f"""
    A {"/".join(selected_colors)} {shape.value}:
    {draw_shape(shape.value, selected_colors)}
    """).center()
    return


@app.cell
def _(mo):
    mo.md("""
    ## Dates
    """)
    return


@app.cell
def _(mo):
    import datetime

    start_date = mo.ui.date(
        label="Start date",
        start=datetime.date(2020, 1, 1),
        stop=datetime.date(2020, 12, 31),
    )
    end_date = mo.ui.date(
        label="End date",
        start=datetime.date(2020, 1, 1),
        stop=datetime.date(2020, 12, 31),
    )
    return end_date, start_date


@app.cell
def _(end_date, mo, start_date):
    mo.hstack(
        [
            mo.hstack([start_date, "➡️", end_date]).left(),
            mo.md(f"From {start_date.value} to {end_date.value}"),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Dropdowns
    """)
    return


@app.cell
def _(mo):
    single = mo.ui.dropdown(
        ["Option 1", "Option 2", "Option 3", "Option 4", "Option 5"],
        label="Single select",
    )
    multi = mo.ui.multiselect(
        ["Option 1", "Option 2", "Option 3", "Option 4", "Option 5"],
        label="Multi select",
        value=["Option 1", "Option 2"],
    )
    mo.hstack([single, multi])
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
