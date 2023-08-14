import marimo

__generated_with = "0.0.5"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("""# UI Elements""")
    return


@app.cell
def __(basic_ui_elements, mo):
    mo.md(
        f"""### Basic elements

        {basic_ui_elements}
        """
    )
    return


@app.cell
def __(basic_ui_elements, construct_element, show_element):
    selected_element = construct_element(basic_ui_elements.value)
    show_element(selected_element)
    return selected_element,


@app.cell
def __(selected_element, value):
    value(selected_element)
    return


@app.cell
def __(composite_elements, mo):
    mo.md(
        f"""### Composite elements

        {composite_elements}
        """
    )
    return


@app.cell
def __(composite_elements, construct_element, show_element):
    composite_element = construct_element(composite_elements.value)
    show_element(composite_element)
    return composite_element,


@app.cell
def __(composite_element, value):
    value(composite_element)
    return


@app.cell
def __(mo):
    composite_elements = mo.ui.dropdown(
        options=dict(sorted({
            'array': mo.ui.array,
            'batch': mo.ui.batch,
            'dictionary': mo.ui.dictionary,
            'form': mo.ui.form,
            'reused-in-markdown': 'reused-in-markdown',
            'reused-in-json': 'reused-in-json',
        }.items())),
    )
    return composite_elements,


@app.cell
def __(mo):
    file_button = lambda: mo.ui.file(kind="button")
    file_area = lambda: mo.ui.file(kind="area")

    basic_ui_elements = mo.ui.dropdown(
        options=dict(
            sorted(
                {
                    "button": mo.ui.button,
                    "checkbox": mo.ui.checkbox,
                    "date": mo.ui.date,
                    "dropdown": mo.ui.dropdown,
                    "file button": file_button,
                    "file area": file_area,
                    "multiselect": mo.ui.multiselect,
                    "number": mo.ui.number,
                    "radio": mo.ui.radio,
                    "slider": mo.ui.slider,
                    "switch": mo.ui.switch,
                    "table": mo.ui.table,
                    "text": mo.ui.text,
                    "text_area": mo.ui.text_area,
                }.items()
            )
        ),
    )
    return basic_ui_elements, file_area, file_button


@app.cell
def __(file_area, file_button, mo):
    def construct_element(value):
        if value == mo.ui.array:
            return mo.ui.array([mo.ui.text(), mo.ui.slider(1, 10), mo.ui.date()])
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
        elif value == 'reused-in-markdown':
            text = mo.ui.text()
            number = mo.ui.number(1, 10)
            return mo.md(f"""
                Text: {text}
                Same Text: {text}
                Number: {number}
                Same Number: {number}
            """)
        elif value == 'reused-in-json':
            text = mo.ui.text()
            number = mo.ui.number(1, 10)
            return mo.as_html([text, number, text, number])
        elif value == mo.ui.dropdown:
            return mo.ui.dropdown(["a", "b", "c"])
        elif value == file_button:
            return file_button()
        elif value == file_area:
            return file_area()
        elif value == mo.ui.form:
            return mo.ui.text_area(placeholder="...").form()
        elif value == mo.ui.multiselect:
            return mo.ui.multiselect(["a", "b", "c"])
        elif value == mo.ui.number:
            return mo.ui.number(start=1, stop=10, step=0.5)
        elif value == mo.ui.radio:
            return mo.ui.radio(["a", "b", "c"], value="a")
        elif value == mo.ui.slider:
            return mo.ui.slider(start=1, stop=10, step=1)
        elif value == mo.ui.switch:
            return mo.ui.switch()
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
    return construct_element,


@app.cell
def __(mo):
    def show_element(element):
        if element is not None:
          return mo.hstack([element], "center")
    return show_element,


@app.cell
def __(mo):
    def value(element):
        def all_values_are_strings(values):
            if values is not None and isinstance(values, list):
                return all(isinstance(v, str) for v in values)

        if element is not None:
            v = (
                element.value
                if not isinstance(element, mo.ui.file)
                else element.name()
            )
            printed_value = (
                mo.as_html(v) if not all_values_are_strings(v) else ", ".join(v)
            )
            return mo.md(
                f"""
                The element's current value is {printed_value}
                """
            )
    return value,


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
