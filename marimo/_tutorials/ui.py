# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.0.5"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        """
        # UI Elements

        One of marimo's most powerful features is its first-class
        support for interactive user interface (UI) elements: interacting
        with a UI element will automatically run cells that reference it.
        """
    )
    return


@app.cell
def __(mo):
    mo.md("## `marimo.ui`")
    return


@app.cell
def __(mo):
    slider = mo.ui.slider(start=1, stop=10, step=1)
    slider

    mo.md(
        f"""
        The `marimo.ui` module has a library of pre-built elements.

        For example, here's a `slider`: {slider}
        """
    )
    return slider,


@app.cell
def __(mo, slider):
    mo.md(f"and here's its value: **{slider.value}**.")
    return


@app.cell
def __(mo):
    mo.md(
        """
        ### How interactions run cells

        Whenever you interact with a UI element, its value is sent back to 
        Python. When this happens, all cells that reference the global variable 
        bound to the UI element, but don't define it, will run.

        This simple rule lets you use UI elements to
        drive the exectution of your program, letting you build
        interactive notebooks and tools for yourselves and others.
        """
    )
    return


@app.cell
def __(mo, slider):
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


@app.cell
def __(mo):
    mo.md(
        """
        ### Simple elements
        """
    )
    return


@app.cell
def __(basic_ui_elements, mo):
    mo.md(
        f"""
        marimo has a large library of simple UI elements: {basic_ui_elements}
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
def __(basic_ui_elements, documentation):
    documentation(basic_ui_elements.value)
    return


@app.cell
def __(composite_elements, mo):
    mo.md(
        f"""### Composite elements

        Composite elements are advanced elements 
        let you build UI elements out of other UI elements.
        Use these powerful elements to logically group together related elements, 
        create a dynamic set of UI elements, or reduce the number of global 
        variables in your program.

        Select a composite element: {composite_elements}
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
def __(composite_elements, documentation):
    documentation(composite_elements.value)
    return


@app.cell
def __(mo):
    mo.md(
        """
        ## Example: A task list

        The next three cells implement a task list. The task list is
        built using three basic UI elements:

        - `mo.checkbox` for the task items
        - `mo.text` for the task entry input
        - `mo.button` for adding and removing tasks

        and one composite element:

        - `mo.array` for maintaining a list of tasks.

        This is an advanced example. You can get far with marimo without
        ever having to implement a stateful element like this one.
        """
    )
    return


@app.cell
def __(mo):
    # A text input for entering a task
    task = mo.ui.text(placeholder="a task ...")

    class TaskListState:
        """
        This class holds the state of the task list: the tasks (labels),
        and whether they've been completed (values).
        """
        def __init__(self):
            # The task labels
            self.labels = []
            # Whether each label is checked
            self.values = []

        def add_task(self):
            if task.value:
                # Add the current value of the task input to `self.labels`
                self.labels.append(task.value)
                # The task starts as incomplete
                self.values.append(False)
            return self

        def clear_tasks(self):
            # Remove all completed tasks from state
            self.labels[:] = [
                label
                for i, label in enumerate(self.labels)
                if not self.values[i]
            ]
            self.values[:] = [v for v in self.values if not v]
            return self

    state = TaskListState()

    # Buttons to add and remove tasks; these buttons mutate state when they
    # are clicked.
    add_task_button = mo.ui.button(
        value=state,
        on_click=lambda state: state.add_task(),
        label="add task",
    )

    clear_tasks_button = mo.ui.button(
        value=state,
        on_click=lambda state: state.clear_tasks(),
        label="clear completed tasks",
    )
    return TaskListState, add_task_button, clear_tasks_button, state, task


@app.cell
def __(add_task_button, clear_tasks_button, mo, state, task):
    # Construct the task list based on the task list state.
    #
    # This cell will re-run and reconstruct the task list with updated state 
    # whenever either of the buttons are clicked, since they include references 
    # to the button elements.
    task_list = mo.ui.array(
        [
            mo.ui.checkbox(value=v, label=l)
            for v, l in zip(state.values, state.labels)
        ],
        label="tasks",
    )

    (
        task,
        add_task_button,
        clear_tasks_button,
        task_list if state.values else mo.md("No tasks! 🎉"),
    )
    return task_list,


@app.cell
def __(state, task_list):
    # This cell runs whenever a task is checked or unchecked, updating the state
    state.values[:] = task_list.value
    return


@app.cell
def __(mo):
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
def __(mo):
    composite_elements = mo.ui.dropdown(
        options=dict(sorted({
            'array': mo.ui.array,
            'batch': mo.ui.batch,
            'dictionary': mo.ui.dictionary,
            'form': mo.ui.form,
        }.items())),
    )
    return composite_elements,


@app.cell
def __(mo):
    basic_ui_elements = mo.ui.dropdown(
        options=dict(sorted({
            'button': mo.ui.button,
            'checkbox': mo.ui.checkbox,
            'date': mo.ui.date,
            'dropdown': mo.ui.dropdown,
            'file': mo.ui.file,
            'multiselect': mo.ui.multiselect,
            'number': mo.ui.number,
            'radio': mo.ui.radio,
            'slider': mo.ui.slider,
            'switch': mo.ui.switch,
            'table': mo.ui.table,
            'text': mo.ui.text,
            'text_area': mo.ui.text_area,
        }.items())),
    )
    return basic_ui_elements,


@app.cell
def __(mo):
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
        elif value == mo.ui.slider:
            return mo.ui.slider(start=1, stop=10, step=0.5)
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
    return value,


@app.cell
def __(mo):
    def documentation(element):
        if element is not None:
            return mo.accordion(
                {f"Documentation on `mo.ui.{element.__name__}`": mo.doc(element)}
            )
    return documentation,


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
