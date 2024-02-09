import marimo

__generated_with = "0.1.61"
app = marimo.App()


@app.cell
def __(np, plt):
    # Generate some random data
    categories = ["A", "B", "C", "D", "E"]
    values = np.random.rand(5)

    bar = plt.bar(categories, values)
    plt.title("Random Bar Chart")
    plt.xlabel("Categories")
    plt.ylabel("Values")
    None
    return bar, categories, values


@app.cell
def __(mo):
    # options
    callout_kind = mo.ui.dropdown(
        label="Color",
        options=["neutral", "danger", "warn", "success", "info"],
        value="info",
    )

    justify = mo.ui.dropdown(
        ["start", "center", "end", "space-between", "space-around"],
        value="space-between",
        label="justify",
    )
    align = mo.ui.dropdown(
        ["start", "center", "end", "stretch"], value="center", label="align"
    )
    gap = mo.ui.number(start=0, step=0.25, stop=2, value=0.25, label="gap")
    wrap = mo.ui.checkbox(label="wrap")
    return align, callout_kind, gap, justify, wrap


@app.cell
def __(alt, callout_kind, mo, office_characters, vega_datasets):
    options = ["Apples", "Oranges", "Pears"]

    # inputs
    button = mo.ui.button(label="Click me")
    checkbox = mo.ui.checkbox(label="check me")
    date = mo.ui.date(label="Start Date")
    dropdown = mo.ui.dropdown(options=options, value=options[0])
    file = mo.vstack([mo.ui.file(kind="button"), mo.ui.file(kind="area")])
    multiselect = mo.ui.multiselect(options=options)
    number = mo.ui.number(start=1, stop=20, label="Number")
    radio = mo.ui.radio(options=options)
    slider = mo.ui.slider(start=1, stop=20, label="Slider", value=3)
    switch = mo.ui.switch(label="do not disturb")
    table = mo.ui.table(data=office_characters, pagination=True)
    text_area = mo.ui.text_area(placeholder="Search...", label="Description")
    text = mo.ui.text(placeholder="Search...", label="Filter")
    refresh = mo.ui.refresh(label="Refresh", options=["1s", "5s", "10s", "30s"])
    microphone = mo.ui.microphone(label="Drop a beat!")
    chart = mo.ui.altair_chart(
        alt.Chart(vega_datasets.data.cars())
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
    )

    # form
    form = mo.ui.text_area(placeholder="...").form()

    # callout
    callout = mo.callout("This is a callout", kind=callout_kind.value)

    # batch
    batch = mo.md("{start} → {end}").batch(
        start=mo.ui.date(label="Start Date"), end=mo.ui.date(label="End Date")
    )

    # status
    # TODO(akshayka): this is using an internal API since we don't expose the progress bar
    progress_bar = mo._plugins.stateless.status._progress.ProgressBar(
        title=None, subtitle=None, total=10
    )

    with mo.status.spinner(title="Hang tight!") as spinner:
        pass

    # stat
    stat = mo.stat(
        value="$100.54",
        label="Open price",
        caption="+2.4%",
        direction="increase",
        bordered=True,
    )
    return (
        batch,
        button,
        callout,
        chart,
        checkbox,
        date,
        dropdown,
        file,
        form,
        microphone,
        multiselect,
        number,
        options,
        progress_bar,
        radio,
        refresh,
        slider,
        spinner,
        stat,
        switch,
        table,
        text,
        text_area,
    )


@app.cell
def __(create_wrapper, mo):
    # array
    wish = mo.ui.text(placeholder="Wish")

    create_wrapper(
        mo.ui.array([wish] * 3, label="Three wishes"),
        "array",
    )
    return wish,


@app.cell
def __(batch, create_wrapper, mo):
    # batch
    create_wrapper(
        mo.hstack([batch, batch.value]),
        "batch",
    )
    return


@app.cell
def __(create_wrapper, mo, refresh):
    # refresh
    create_wrapper(mo.hstack([refresh, refresh.value]), "refresh")
    return


@app.cell
def __(button, create_wrapper, mo):
    # button
    create_wrapper(
        mo.hstack([button]),
        "button",
    )
    return


@app.cell
def __(checkbox, create_wrapper, mo):
    # checkbox
    create_wrapper(
        mo.hstack([checkbox, mo.md(f"Has value: {checkbox.value}")]),
        "checkbox",
    )
    return


@app.cell
def __(create_wrapper, mo):
    # dictionary
    first_name = mo.ui.text(placeholder="First name")
    last_name = mo.ui.text(placeholder="Last name")
    email = mo.ui.text(placeholder="Email", kind="email")

    create_wrapper(
        mo.ui.dictionary(
            {
                "First name": first_name,
                "Last name": last_name,
                "Email": email,
            }
        ),
        "dictionary",
    )
    return email, first_name, last_name


@app.cell
def __(callout, callout_kind, create_wrapper, mo):
    create_wrapper(
        mo.vstack([callout_kind, callout], align="stretch", gap=0),
        "callout",
    )
    return


@app.cell
def __(create_wrapper, mo):
    create_wrapper(
        mo.md(
            f"""
    # Hello world!
    ## **Hello world!**
    ## *Hello world!*
    ## **_Hello world!_**

    `marimo` _supports_ **markdown**

    > And Blockquotes

    ```python
    # And code
    import marimo as mo
    import numpy as np
    ```

    - And
    - Lists

    1. And
    2. Ordered
    3. Lists

    [And](https://www.youtube.com/watch?v=dQw4w9WgXcQ) Links
    """
        ),
        "markdown",
    )
    return


@app.cell
def __(create_wrapper, mo):
    create_wrapper(
        mo.md(
            r"""
        The exponential function $f(x) = e^x$ can be represented as

        \[
            f(x) = 1 + x + \frac{x^2}{2!} + \frac{x^3}{3!} + \ldots.
        \]
        """
        ),
        "latex",
    )
    return


@app.cell
def __(create_wrapper, file):
    create_wrapper(
        file,
        "file",
    )
    return


@app.cell
def __(create_wrapper, mo, multiselect):
    create_wrapper(
        mo.hstack([multiselect, mo.md(f"Has value: {multiselect.value}")]),
        "multiselect",
    )
    return


@app.cell
def __(create_wrapper, dropdown, mo):
    create_wrapper(
        mo.hstack([dropdown, mo.md(f"Has value: {dropdown.value}")]),
        "dropdown",
    )
    return


@app.cell
def __(create_wrapper, date, mo):
    create_wrapper(
        mo.hstack([date, mo.md(f"Has value: {date.value}")]),
        "date",
    )
    return


@app.cell
def __(create_wrapper, mo, switch):
    create_wrapper(
        mo.hstack([switch, mo.md(f"Has value: {switch.value}")]),
        "switch",
    )
    return


@app.cell
def __(create_wrapper, microphone, mo):
    # microphone
    create_wrapper(
        mo.hstack([microphone, mo.audio(microphone.value)]),
        "microphone",
    )
    return


@app.cell
def __(create_wrapper, mo, slider):
    create_wrapper(
        mo.hstack([slider, mo.md(f"Has value: {slider.value}")]),
        "slider",
    )
    return


@app.cell
def __(create_wrapper, mo):
    _src = "https://upload.wikimedia.org/wikipedia/commons/8/8c/Ivan_Ili%C4%87-Chopin_-_Prelude_no._1_in_C_major.ogg"
    create_wrapper(
        mo.audio(_src),
        "audio",
    )
    return


@app.cell
def __(create_wrapper, mo):
    create_wrapper(
        mo.pdf(
            src="https://arxiv.org/pdf/2104.00282.pdf",
            width="100%",
            height="200px",
        ),
        "pdf",
    )
    return


@app.cell
def __(create_wrapper, mo):
    _src = (
        "https://images.pexels.com/photos/86596/owl-bird-eyes-eagle-owl-86596.jpeg"
    )
    create_wrapper(
        mo.image(src=_src, width=280, rounded=True),
        "image",
    )
    return


@app.cell
def __(create_wrapper, mo, number):
    create_wrapper(
        mo.hstack([number, mo.md(f"Has value: {number.value}")]),
        "number",
    )
    return


@app.cell
def __(mo):
    def create_wrapper(element, key, code=""):
        return mo.vstack(
            [mo.md(f"## **{key.upper()}**"), element], align="stretch", gap=2
        )
    return create_wrapper,


@app.cell
def __(create_wrapper, mo, text):
    create_wrapper(
        mo.hstack([text, mo.md(f"Has value: {text.value}")]),
        "text",
    )
    return


@app.cell
def __(create_wrapper, mo, text_area):
    create_wrapper(
        mo.hstack([text_area, mo.md(f"Has value: {text_area.value}")]),
        "text_area",
    )
    return


@app.cell
def __(create_wrapper, mo, radio):
    create_wrapper(
        mo.hstack([radio, mo.md(f"Has value: {radio.value}")]),
        "radio",
    )
    return


@app.cell
def __(create_wrapper, form, mo):
    create_wrapper(
        mo.hstack([form, mo.md(f"Has value: {form.value}")]),
        "form",
    )
    return


@app.cell
def __(create_wrapper, mo):
    create_wrapper(
        mo.accordion(
            {
                "Door 1": mo.md("Nothing!"),
                "Door 2": mo.md("Nothing!"),
                "Door 3": mo.image(
                    "https://images.unsplash.com/photo-1524024973431-2ad916746881",
                    height=150,
                ),
            }
        ),
        "accordion",
    )
    return


@app.cell
def __(bar, create_wrapper, mo):
    create_wrapper(
        mo.ui.tabs(
            {
                "📈 Sales": bar,
                "💻 Settings": mo.ui.text(placeholder="Key"),
            }
        ),
        "tabs",
    )
    return


@app.cell
def __(create_wrapper, mo):
    tree = mo.tree(
        [
            "entry",
            "another entry",
            {"key": [0, mo.ui.slider(1, 10, value=5), 2]},
        ],
        label="A tree of elements.",
    )

    create_wrapper(
        tree,
        "tree",
    )
    return tree,


@app.cell
def __(align, boxes, create_wrapper, gap, justify, mo, wrap):
    horizontal = mo.hstack(
        boxes,
        align=align.value,
        justify=justify.value,
        gap=gap.value,
        wrap=wrap.value,
    )
    vertical = mo.vstack(
        boxes,
        align=align.value,
        gap=gap.value,
    )

    stacks = mo.vstack(
        [
            mo.hstack([justify, align, gap], justify="center"),
            horizontal,
            mo.md("-----------------------------"),
            vertical,
        ],
        align="stretch",
        gap=1,
    )

    create_wrapper(
        stacks,
        "stacks",
    )
    return horizontal, stacks, vertical


@app.cell
def __(create_wrapper, table):
    create_wrapper(
        table, "table", "mo.ui.table(data=office_characters, pagination=True)"
    )
    return


@app.cell
def __(create_wrapper, spinner):
    # spinner
    create_wrapper(
        spinner,
        "spinner",
    )
    return


@app.cell
def __(create_wrapper, progress_bar):
    # progress bar
    create_wrapper(
        progress_bar,
        "progress-bar",
    )
    return


@app.cell
def __(create_wrapper, stat):
    create_wrapper(
        stat,
        "stat",
    )
    return


@app.cell
def __(chart, create_wrapper, mo):
    create_wrapper(
        mo.vstack([chart, mo.ui.table(chart.value)]),
        "altair-chart",
    )
    return


@app.cell
def __(mo):
    def create_box(num=1):
        box_size = 30 + num * 10
        return mo.Html(
            f"<div style='min-width: {box_size}px; min-height: {box_size}px; background-color: orange; text-align: center; line-height: {box_size}px'>{str(num)}</div>"
        )


    boxes = [create_box(i) for i in range(1, 5)]
    return boxes, create_box


@app.cell
def __():
    office_characters = [
        {"first_name": "Michael", "last_name": "Scott"},
        {"first_name": "Jim", "last_name": "Halpert"},
        {"first_name": "Pam", "last_name": "Beesly"},
        {"first_name": "Dwight", "last_name": "Schrute"},
        {"first_name": "Angela", "last_name": "Martin"},
        {"first_name": "Kevin", "last_name": "Malone"},
        {"first_name": "Oscar", "last_name": "Martinez"},
        {"first_name": "Stanley", "last_name": "Hudson"},
        {"first_name": "Phyllis", "last_name": "Vance"},
        {"first_name": "Meredith", "last_name": "Palmer"},
        {"first_name": "Creed", "last_name": "Bratton"},
        {"first_name": "Ryan", "last_name": "Howard"},
        {"first_name": "Kelly", "last_name": "Kapoor"},
        {"first_name": "Toby", "last_name": "Flenderson"},
        {"first_name": "Darryl", "last_name": "Philbin"},
        {"first_name": "Erin", "last_name": "Hannon"},
        {"first_name": "Andy", "last_name": "Bernard"},
        {"first_name": "Jan", "last_name": "Levinson"},
        {"first_name": "David", "last_name": "Wallace"},
        {"first_name": "Holly", "last_name": "Flax"},
    ]
    return office_characters,


@app.cell
def __():
    import altair as alt
    import vega_datasets
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    return alt, mo, np, plt, vega_datasets


if __name__ == "__main__":
    app.run()
