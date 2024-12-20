# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.10.6"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # UI Elements

        One of marimo's most powerful features is its first-class
        support for interactive user interface (UI) elements: interacting
        with a UI element will automatically run cells that reference it.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## marimo.ui""")
    return


@app.cell
def _(mo):
    slider = mo.ui.slider(start=1, stop=10, step=1)
    slider

    mo.md(
        f"""
        The `marimo.ui` module has a library of pre-built elements.

        For example, here's a `slider`: {slider}
        """
    )
    return (slider,)


@app.cell
def _(mo, slider):
    mo.md(f"and here's its value: **{slider.value}**.")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ### How interactions run cells

        Whenever you interact with a UI element, its value is sent back to 
        Python. When this happens, all cells that reference the global variable 
        bound to the UI element, but don't define it, will run.

        This simple rule lets you use UI elements to
        drive the execution of your program, letting you build
        interactive notebooks and tools for yourselves and others.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo, slider):
    mo.accordion(
        {
            "Tip: assign UI elements to global variables": (
                """
                Interacting with a displayed UI element will only 
                trigger reactive execution if the UI element is assigned
                to a global variable.
                """
            ),
            "Tip: accessing an element's value": (
                """
                Every UI element has a value attribute that you can access in 
                Python.
                """
            ),
            "Tip: embed UI elements in markdown": mo.md(
                f"""
                You can embed UI elements in markdown using f-strings.

                For example, we can render the slider here: {slider}
                """
            ),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""### Simple elements""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""marimo has a [large library of simple UI elements](https://docs.marimo.io/api/inputs/index.html). Here are a just few examples:""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        See our [examples folder](https://github.com/marimo-team/marimo/tree/main/examples/ui) on GitHub for bite-sized notebooks showcasing all our UI elements. For
        a more detailed reference, see our [API docs](https://docs.marimo.io/api/inputs/).
        """
    ).callout()
    return


@app.cell
def _(mo):
    number = mo.ui.number(start=1, stop=10, step=1)
    number
    return (number,)


@app.cell
def _(number):
    number.value
    return


@app.cell
def _(mo):
    checkbox = mo.ui.checkbox(label="checkbox")
    checkbox
    return (checkbox,)


@app.cell
def _(checkbox):
    checkbox.value
    return


@app.cell
def _(mo):
    text = mo.ui.text(placeholder="type some text ...")
    text
    return (text,)


@app.cell
def _(text):
    text.value
    return


@app.cell
def _(mo):
    text_area = mo.ui.text_area(placeholder="type some text ...")
    text_area
    return (text_area,)


@app.cell
def _(text_area):
    text_area.value
    return


@app.cell
def _(mo):
    dropdown = mo.ui.dropdown(["a", "b", "c"])
    dropdown
    return (dropdown,)


@app.cell
def _(dropdown):
    dropdown.value
    return


@app.cell
def _(mo):
    run_button = mo.ui.run_button(label="click me")
    run_button
    return (run_button,)


@app.cell
def _(run_button):
    "Run button was clicked!" if run_button.value else "Click the run button!"
    return


@app.cell
def _(mo):
    file_upload = mo.ui.file(kind="area")
    file_upload
    return (file_upload,)


@app.cell
def _(file_upload):
    file_upload.value
    return


@app.cell
def _(basic_ui_elements, mo):
    mo.md(f"To see more examples, use this dropdown: {basic_ui_elements}")
    return


@app.cell
def _(basic_ui_elements, construct_element, show_element):
    selected_element = construct_element(basic_ui_elements.value)
    show_element(selected_element)
    return (selected_element,)


@app.cell
def _(selected_element, value):
    value(selected_element)
    return


@app.cell
def _(basic_ui_elements, documentation):
    documentation(basic_ui_elements.value)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ### Composite elements

            Composite elements are advanced elements 
            let you build UI elements out of other UI elements. 

            Use these powerful elements to logically group together related elements, 
            create a dynamic set of UI elements, or reduce the number of global 
            variables in your program.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        This first example shows how to create an array of UI elements using `mo.ui.array`.
        When you interact with an element in the array, all cells that reference the
        array are reactively run. If you instead used a regular Python list, cells referring to the list would _not_ be run.
        """
    )
    return


@app.cell
def _(mo):
    array = mo.ui.array(
        [mo.ui.text(), mo.ui.slider(start=1, stop=10), mo.ui.date()]
    )
    array
    return (array,)


@app.cell
def _(array):
    array.value
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""marimo also comes with `mo.ui.dictionary`, which is analogous to `mo.ui.array`""")
    return


@app.cell
def _(mo):
    dictionary = mo.ui.dictionary(
        {
            "text": mo.ui.text(),
            "slider": mo.ui.slider(start=1, stop=10),
            "date": mo.ui.date(),
        }
    )
    dictionary
    return (dictionary,)


@app.cell
def _(dictionary):
    dictionary.value
    return


@app.cell(hide_code=True)
def _(composite_elements, mo):
    mo.md(
        f"To see additional composite elements, use this dropdown: {composite_elements}"
    )
    return


@app.cell
def _(composite_elements, construct_element, show_element):
    composite_element = construct_element(composite_elements.value)
    show_element(composite_element)
    return (composite_element,)


@app.cell
def _(composite_element, value):
    value(composite_element)
    return


@app.cell
def _(composite_elements, documentation):
    documentation(composite_elements.value)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ### Building custom elements

        marimo supports third-party UI elements through anywidget — this lets you build
        your own interactive UI elements, or use widgets built by others in the
        community. To learn more, [see our
        docs](https://docs.marimo.io/guides/integrating_with_marimo/custom_ui_plugins.html).
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## Appendix
        The remaining cells are helper data structures and functions.
        You can look at their code if you're curious how certain parts of this 
        tutorial were implemented.
        """
    )
    return


@app.cell
def _(mo):
    composite_elements = mo.ui.dropdown(
        options=dict(
            sorted(
                {
                    "array": mo.ui.array,
                    "batch": mo.ui.batch,
                    "dictionary": mo.ui.dictionary,
                    "form": mo.ui.form,
                }.items()
            )
        ),
        allow_select_none=True
    )
    return (composite_elements,)


@app.cell
def _(mo):
    basic_ui_elements = mo.ui.dropdown(
        options=dict(
            sorted(
                {
                    "button": mo.ui.button,
                    "checkbox": mo.ui.checkbox,
                    "date": mo.ui.date,
                    "dropdown": mo.ui.dropdown,
                    "file": mo.ui.file,
                    "multiselect": mo.ui.multiselect,
                    "number": mo.ui.number,
                    "radio": mo.ui.radio,
                    "range_slider": mo.ui.range_slider,
                    "slider": mo.ui.slider,
                    "switch": mo.ui.switch,
                    "tabs": mo.ui.tabs,
                    "table": mo.ui.table,
                    "text": mo.ui.text,
                    "text_area": mo.ui.text_area,
                }.items()
            )
        ),
    )
    return (basic_ui_elements,)


@app.cell
def _(mo):
    def construct_element(value):
        if value == mo.ui.array:
            return mo.ui.array(
                [mo.ui.text(), mo.ui.slider(1, 10), mo.ui.date()]
            )
        elif value == mo.ui.batch:
            return mo.md(
                """
                - Name: {name}
                - Date: {date}
                """
            ).batch(name=mo.ui.text(), date=mo.ui.date())
        elif value == mo.ui.button:
            return mo.ui.button(
                value=0, label="click me", on_click=lambda value: value + 1
            )
        elif value == mo.ui.checkbox:
            return mo.ui.checkbox(label="check me")
        elif value == mo.ui.date:
            return mo.ui.date()
        elif value == mo.ui.dictionary:
            return mo.ui.dictionary(
                {
                    "slider": mo.ui.slider(1, 10),
                    "text": mo.ui.text("type something!"),
                    "array": mo.ui.array(
                        [
                            mo.ui.button(value=0, on_click=lambda v: v + 1)
                            for _ in range(3)
                        ],
                        label="buttons",
                    ),
                }
            )
        elif value == mo.ui.dropdown:
            return mo.ui.dropdown(["a", "b", "c"])
        elif value == mo.ui.file:
            return [mo.ui.file(kind="button"), mo.ui.file(kind="area")]
        elif value == mo.ui.form:
            return mo.ui.text_area(placeholder="...").form()
        elif value == mo.ui.multiselect:
            return mo.ui.multiselect(["a", "b", "c"])
        elif value == mo.ui.number:
            return mo.ui.number(start=1, stop=10, step=0.5)
        elif value == mo.ui.radio:
            return mo.ui.radio(["a", "b", "c"], value="a")
        elif value == mo.ui.range_slider:
            return mo.ui.range_slider(start=1, stop=10, step=0.5)
        elif value == mo.ui.slider:
            return mo.ui.slider(start=1, stop=10, step=0.5)
        elif value == mo.ui.switch:
            return mo.ui.switch()
        elif value == mo.ui.tabs:
            return mo.ui.tabs(
                {
                    "Employee #1": {
                        "first_name": "Michael",
                        "last_name": "Scott",
                    },
                    "Employee #2": {
                        "first_name": "Dwight",
                        "last_name": "Schrute",
                    },
                }
            )
        elif value == mo.ui.table:
            return mo.ui.table(
                data=[
                    {"first_name": "Michael", "last_name": "Scott"},
                    {"first_name": "Dwight", "last_name": "Schrute"},
                ],
                label="Employees",
            )
        elif value == mo.ui.text:
            return mo.ui.text()
        elif value == mo.ui.text_area:
            return mo.ui.text_area()
        return None
    return (construct_element,)


@app.cell
def _(mo):
    def show_element(element):
        if element is not None:
            return mo.hstack([element], justify="center")
    return (show_element,)


@app.cell
def _(mo):
    def value(element):
        if element is not None:
            v = (
                element.value
                if not isinstance(element, mo.ui.file)
                else element.name()
            )
            return mo.md(
                f"""
                The element's current value is {mo.as_html(element.value)}
                """
            )
    return (value,)


@app.cell
def _(mo):
    def documentation(element):
        if element is not None:
            return mo.accordion(
                {
                    f"Documentation on `mo.ui.{element.__name__}`": mo.doc(
                        element
                    )
                }
            )
    return (documentation,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
