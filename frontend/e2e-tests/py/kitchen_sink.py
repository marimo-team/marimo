# /// script
# dependencies = [
#     "altair==6.0.0",
#     "marimo>=0.19.4",
#     "matplotlib==3.10.8",
#     "numpy==2.4.1",
#     "plotly==6.5.2",
#     "vega-datasets==0.9.0",
# ]
# [tool.marimo.runtime]
# auto_instantiate = true
# [tool.marimo.experimental]
# server_side_pdf_export = true
# ///

import marimo

__generated_with = "0.19.6"
app = marimo.App(auto_download=["ipynb"])


@app.cell
def _(np, plt):
    # Generate some random data
    categories = ["A", "B", "C", "D", "E"]
    values = np.random.rand(5)

    bar = plt.bar(categories, values)
    plt.title("Random Bar Chart")
    plt.xlabel("Categories")
    plt.ylabel("Values")
    return (bar,)


@app.cell
def _(mo):
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
def _(alt, callout_kind, mo, office_characters, px, vega_datasets):
    options = ["Apples", "Oranges", "Pears"]

    # Basic inputs
    button = mo.ui.button(label="Click me")
    run_button = mo.ui.run_button(label="Run computation")
    checkbox = mo.ui.checkbox(label="check me")
    switch = mo.ui.switch(label="do not disturb")

    # Text inputs
    text = mo.ui.text(placeholder="Search...", label="Filter")
    text_area = mo.ui.text_area(placeholder="Search...", label="Description")
    code_editor = mo.ui.code_editor(
        value="def hello():\n    return 'world'",
        language="python",
        min_height=100,
    )

    # Number inputs
    number = mo.ui.number(start=1, stop=20, label="Number")
    slider = mo.ui.slider(start=1, stop=20, label="Slider", value=3)
    range_slider = mo.ui.range_slider(
        start=0, stop=100, value=[20, 80], label="Range"
    )

    # Selection inputs
    dropdown = mo.ui.dropdown(options=options, value=options[0])
    multiselect = mo.ui.multiselect(options=options)
    radio = mo.ui.radio(options=options)

    # Date/time inputs
    date = mo.ui.date(label="Start Date")
    date_range = mo.ui.date_range(label="Date Range")
    datetime_picker = mo.ui.datetime(label="Date and Time")

    # File inputs
    file = mo.vstack([mo.ui.file(kind="button"), mo.ui.file(kind="area")])
    refresh = mo.ui.refresh(label="Refresh", options=["1s", "5s", "10s", "30s"])
    microphone = mo.ui.microphone(label="Drop a beat!")

    # Data components
    table = mo.ui.table(data=office_characters, pagination=True)
    _cars_df = vega_datasets.data.cars()
    dataframe_transformer = mo.ui.dataframe(_cars_df)

    # Chart components
    chart = mo.ui.altair_chart(
        alt.Chart(_cars_df)
        .mark_point()
        .encode(x="Horsepower", y="Miles_per_Gallon", color="Origin")
    )

    figure = px.scatter(
        _cars_df,
        x="Horsepower",
        y="Miles_per_Gallon",
        color="Origin",
        hover_data=["Name", "Horsepower", "Miles_per_Gallon", "Origin"],
        title="Car Horsepower vs. Miles per Gallon",
        labels={
            "Horsepower": "Horsepower",
            "Miles_per_Gallon": "Miles per Gallon",
            "Origin": "Origin",
        },
    )
    plotly_chart = mo.ui.plotly(figure)

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
        title=None, subtitle=None, total=10, show_rate=True, show_eta=True
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
        code_editor,
        dataframe_transformer,
        date,
        date_range,
        datetime_picker,
        dropdown,
        file,
        form,
        microphone,
        multiselect,
        number,
        plotly_chart,
        progress_bar,
        radio,
        range_slider,
        refresh,
        run_button,
        slider,
        spinner,
        stat,
        switch,
        table,
        text,
        text_area,
    )


@app.cell
def _(create_wrapper, mo):
    # array
    wish = mo.ui.text(placeholder="Wish")

    create_wrapper(
        mo.ui.array([wish] * 3, label="Three wishes"),
        "array",
    )
    return


@app.cell
def _(batch, create_wrapper, mo):
    # batch
    create_wrapper(
        mo.hstack([batch, batch.value]),
        "batch",
    )
    return


@app.cell
def _(create_wrapper, mo, refresh):
    # refresh
    create_wrapper(mo.hstack([refresh, refresh.value]), "refresh")
    return


@app.cell
def _(button, create_wrapper, mo):
    # button
    create_wrapper(
        mo.hstack([button]),
        "button",
    )
    return


@app.cell
def _(create_wrapper, mo, run_button):
    # run_button
    create_wrapper(
        mo.hstack([run_button, mo.md(f"Clicked: {run_button.value}")]),
        "run_button",
    )
    return


@app.cell
def _(checkbox, create_wrapper, mo):
    # checkbox
    create_wrapper(
        mo.hstack([checkbox, mo.md(f"Has value: {checkbox.value}")]),
        "checkbox",
    )
    return


@app.cell
def _(create_wrapper, mo):
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
    return


@app.cell
def _(callout, callout_kind, create_wrapper, mo):
    create_wrapper(
        mo.vstack([callout_kind, callout], align="stretch", gap=0),
        "callout",
    )
    return


@app.cell
def _(create_wrapper, mo):
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
def _(create_wrapper, mo):
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
def _(create_wrapper, file):
    create_wrapper(
        file,
        "file",
    )
    return


@app.cell
def _(create_wrapper, mo, multiselect):
    create_wrapper(
        mo.hstack([multiselect, mo.md(f"Has value: {multiselect.value}")]),
        "multiselect",
    )
    return


@app.cell
def _(create_wrapper, dropdown, mo):
    create_wrapper(
        mo.hstack([dropdown, mo.md(f"Has value: {dropdown.value}")]),
        "dropdown",
    )
    return


@app.cell
def _(create_wrapper, date, mo):
    create_wrapper(
        mo.hstack([date, mo.md(f"Has value: {date.value}")]),
        "date",
    )
    return


@app.cell
def _(create_wrapper, date_range, mo):
    # date_range
    create_wrapper(
        mo.hstack([date_range, mo.md(f"Has value: {date_range.value}")]),
        "date_range",
    )
    return


@app.cell
def _(create_wrapper, datetime_picker, mo):
    # datetime
    create_wrapper(
        mo.hstack([datetime_picker, mo.md(f"Has value: {datetime_picker.value}")]),
        "datetime",
    )
    return


@app.cell
def _(create_wrapper, mo, switch):
    create_wrapper(
        mo.hstack([switch, mo.md(f"Has value: {switch.value}")]),
        "switch",
    )
    return


@app.cell
def _(create_wrapper, microphone, mo):
    # microphone
    has_audio_content = len(microphone.value.getbuffer()) != 0
    create_wrapper(
        mo.hstack(
            [
                microphone,
                mo.audio(microphone.value)
                if has_audio_content
                else mo.md("Waiting..."),
            ]
        ),
        "microphone",
    )
    return


@app.cell
def _(create_wrapper, mo, slider):
    create_wrapper(
        mo.hstack([slider, mo.md(f"Has value: {slider.value}")]),
        "slider",
    )
    return


@app.cell
def _(create_wrapper, mo, range_slider):
    # range_slider
    create_wrapper(
        mo.hstack([range_slider, mo.md(f"Has value: {range_slider.value}")]),
        "range_slider",
    )
    return


@app.cell
def _(create_wrapper, mo):
    _src = "https://upload.wikimedia.org/wikipedia/commons/8/8c/Ivan_Ili%C4%87-Chopin_-_Prelude_no._1_in_C_major.ogg"
    create_wrapper(
        mo.audio(_src),
        "audio",
    )
    return


@app.cell
def _(create_wrapper, mo):
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
def _(create_wrapper, mo):
    _src = (
        "https://images.pexels.com/photos/86596/owl-bird-eyes-eagle-owl-86596.jpeg"
    )
    create_wrapper(
        mo.image(src=_src, width=280, rounded=True),
        "image",
    )
    return


@app.cell
def _(create_wrapper, mo, number):
    create_wrapper(
        mo.hstack([number, mo.md(f"Has value: {number.value}")]),
        "number",
    )
    return


@app.cell
def _(mo):
    def create_wrapper(element, key, code=""):
        return mo.vstack(
            [mo.md(f"## **{key.upper()}**"), element], align="stretch", gap=2
        )
    return (create_wrapper,)


@app.cell
def _(create_wrapper, mo, text):
    create_wrapper(
        mo.hstack([text, mo.md(f"Has value: {text.value}")]),
        "text",
    )
    return


@app.cell
def _(create_wrapper, mo, text_area):
    create_wrapper(
        mo.hstack([text_area, mo.md(f"Has value: {text_area.value}")]),
        "text_area",
    )
    return


@app.cell
def _(code_editor, create_wrapper, mo):
    # code_editor
    create_wrapper(
        mo.vstack([code_editor, mo.md(f"```python\n{code_editor.value}\n```")]),
        "code_editor",
    )
    return


@app.cell
def _(create_wrapper, mo, radio):
    create_wrapper(
        mo.hstack([radio, mo.md(f"Has value: {radio.value}")]),
        "radio",
    )
    return


@app.cell
def _(create_wrapper, form, mo):
    create_wrapper(
        mo.hstack([form, mo.md(f"Has value: {form.value}")]),
        "form",
    )
    return


@app.cell
def _(create_wrapper, mo):
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
def _(bar, create_wrapper, mo):
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
def _(create_wrapper, mo):
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
    return


@app.cell
def _(align, boxes, create_wrapper, gap, justify, mo, wrap):
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
    return


@app.cell
def _(create_wrapper, table):
    create_wrapper(
        table, "table", "mo.ui.table(data=office_characters, pagination=True)"
    )
    return


@app.cell
def _(create_wrapper, dataframe_transformer, mo):
    # dataframe transformer
    create_wrapper(
        mo.vstack(
            [dataframe_transformer, mo.ui.table(dataframe_transformer.value)]
        ),
        "dataframe_transformer",
    )
    return


@app.cell
def _(create_wrapper, spinner):
    # spinner
    create_wrapper(
        spinner,
        "spinner",
    )
    return


@app.cell
def _(create_wrapper, progress_bar):
    # progress bar
    create_wrapper(
        progress_bar,
        "progress-bar",
    )
    return


@app.cell
def _(create_wrapper, stat):
    create_wrapper(
        stat,
        "stat",
    )
    return


@app.cell
def _(chart, create_wrapper, mo):
    create_wrapper(
        mo.vstack([chart, mo.ui.table(chart.value)]),
        "altair-chart",
    )
    return


@app.cell
def _(create_wrapper, mo, plotly_chart):
    create_wrapper(
        mo.vstack([plotly_chart, mo.ui.table(plotly_chart.value)]), "plotly-chart"
    )
    return


@app.cell
def _(create_wrapper, mo):
    # video
    _video_src = "https://www.youtube.com/watch?v=5ZxczGlrkyQ"
    create_wrapper(
        mo.video(src=_video_src, width=400),
        "video",
    )
    return


@app.cell
def _(create_wrapper, mo):
    # download button
    data_to_download = "Hello, this is the file content!\nLine 2\nLine 3"
    create_wrapper(
        mo.download(
            data=data_to_download.encode(),
            filename="sample.txt",
            label="Download Sample File",
        ),
        "download",
    )
    return


@app.cell
def _(create_wrapper, mo):
    # json display
    sample_json = {
        "name": "marimo",
        "version": "0.19.6",
        "features": ["reactive", "interactive", "reproducible"],
        "nested": {"key1": "value1", "key2": [1, 2, 3]},
    }
    create_wrapper(
        mo.json(sample_json),
        "json",
    )
    return


@app.cell
def _(create_wrapper, mo):
    # mermaid diagram
    create_wrapper(
        mo.mermaid(
            """
            graph TD
                A[Start] --> B{Decision}
                B -->|Yes| C[Do Something]
                B -->|No| D[Do Something Else]
                C --> E[End]
                D --> E
            """
        ),
        "mermaid",
    )
    return


@app.cell
def _(create_wrapper, mo):
    # icon
    create_wrapper(
        mo.hstack(
            [
                mo.icon("lucide:home", size=24),
                mo.icon("lucide:settings", size=24),
                mo.icon("lucide:user", size=24),
                mo.icon("lucide:star", size=24, color="gold"),
                mo.icon("lucide:heart", size=24, color="red"),
            ],
            gap=1,
        ),
        "icon",
    )
    return


@app.cell
def _(create_wrapper, mo):
    # center, left, right alignment
    create_wrapper(
        mo.vstack(
            [
                mo.left(mo.md("**Left aligned**")),
                mo.center(mo.md("**Center aligned**")),
                mo.right(mo.md("**Right aligned**")),
            ],
            align="stretch",
        ),
        "alignment (left/center/right)",
    )
    return


@app.cell
def _(create_wrapper, mo):
    # carousel
    _images = [
        "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400",
        "https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=400",
        "https://images.unsplash.com/photo-1426604966848-d7adac402bff?w=400",
    ]
    create_wrapper(
        mo.carousel(
            [mo.image(src=img, width=300, rounded=True) for img in _images]
        ),
        "carousel",
    )
    return


@app.cell
def _(create_wrapper, mo):
    # Html component
    create_wrapper(
        mo.Html(
            """
            <div style="padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; color: white;">
                <h3 style="margin: 0;">Custom HTML</h3>
                <p style="margin: 10px 0 0 0;">This is raw HTML content with custom styling.</p>
            </div>
            """
        ),
        "Html",
    )
    return


@app.cell
def _(create_wrapper, mo):
    # style wrapper
    styled_content = mo.md("This content has custom styling applied")
    create_wrapper(
        mo.style(
            styled_content,
            {
                "background": "#f0f9ff",
                "padding": "16px",
                "border-radius": "8px",
                "border": "2px solid #0ea5e9",
            },
        ),
        "style",
    )
    return


@app.cell
def _(create_wrapper, mo):
    # as_html conversion
    class CustomObject:
        def __repr__(self):
            return "CustomObject(value=42)"


    create_wrapper(
        mo.as_html([1, 2, 3, {"key": "value"}]),
        "as_html",
    )
    return


@app.cell
def _(create_wrapper, mo):
    # nav_menu
    create_wrapper(
        mo.nav_menu(
            {
                "#section1": "Section 1",
                "#section2": "Section 2",
                "Links": {
                    "https://marimo.io": "marimo.io",
                    "https://github.com/marimo-team/marimo": "GitHub",
                },
            },
            orientation="horizontal",
        ),
        "nav_menu",
    )
    return


@app.cell
def _(create_wrapper, mo):
    # lazy loading
    def expensive_component():
        return mo.md("This content was **lazily loaded**!")


    create_wrapper(
        mo.lazy(expensive_component),
        "lazy",
    )
    return


@app.cell
def _(create_wrapper, mo):
    # show_code - display code with syntax highlighting
    code_sample = '''
    def fibonacci(n):
    """Calculate the nth Fibonacci number."""
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

    # Usage
    result = fibonacci(10)
    print(f"The 10th Fibonacci number is {result}")
    '''
    create_wrapper(
        mo.show_code(code_sample),
        "show_code",
    )
    return


@app.cell
def _(create_wrapper, mo):
    # chat component (without model, just UI)
    def simple_chat_model(messages, config):
        # Echo bot for demonstration
        return f"You said: {messages[-1].content}"


    chat = mo.ui.chat(simple_chat_model, prompts=["Hello!", "How are you?"])
    create_wrapper(chat, "chat")
    return


@app.cell
def _(mo):
    # sidebar example
    mo.sidebar(
        mo.vstack(
            [
                mo.md("# Menu"),
                mo.ui.button(label="Home"),
                mo.ui.button(label="Settings"),
            ]
        )
    )
    return


@app.cell
def _(mo):
    def create_box(num=1):
        box_size = 30 + num * 10
        return mo.Html(
            f"<div style='min-width: {box_size}px; min-height: {box_size}px; background-color: orange; text-align: center; line-height: {box_size}px'>{str(num)}</div>"
        )


    boxes = [create_box(i) for i in range(1, 5)]
    return (boxes,)


@app.cell
def _():
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
    return (office_characters,)


@app.cell
def _():
    import altair as alt
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import plotly.express as px
    import vega_datasets
    return alt, mo, np, plt, px, vega_datasets


if __name__ == "__main__":
    app.run()
