# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.2.2"
app = marimo.App()


@app.cell(hide_code=True)
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


@app.cell(hide_code=True)
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


@app.cell(hide_code=True)
def __(mo):
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


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ### Simple elements
        """
    )
    return


@app.cell(hide_code=True)
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


@app.cell(hide_code=True)
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
    mo.md("## State")
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        **Heads up!**

        The rest of this tutorial covers state, an advanced topic. Feel free
        to return here later, if or when you find yourself
        limited in building interactive stateful apps.
        """
    ).callout(kind="warn")
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        You can build powerful interactive notebooks and apps using just
        `mo.ui` and reactivity.

        Sometimes, however, you might want interactions to mutate **state**. 
        Maybe you're building a checklist, and you want to maintain a list
        of action items. Or maybe you want to tie two different UI elements, so 
        that updating one updates the other. 

        For these and other cases, marimo provides the function `mo.state`, which
        creates state returns a getter function and a setter function. When you 
        call the setter function in one cell, all other 
        cells that reference the getter via a global variable are automatically 
        run (similar to UI elements).
        """
    )
    return


@app.cell
def __(mo):
    mo.accordion({"Documentation on `mo.state`": mo.doc(mo.state)})
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ### Creating state

        `mo.state` takes an initial state value as its argument, and returns

        - a function that returns the state value;
        - a function that updates the state value.

        For exaxmple,

        ```python
        get_counter, set_counter = mo.state(0)
        ```
        """
    )
    return


@app.cell
def __(mo):
    get_counter, set_counter = mo.state(0)
    return get_counter, set_counter


@app.cell(hide_code=True)
def __(mo):
    mo.accordion(
        {
            "Tip: assign state getters to global variables": (
                """
                Calling a state's setter function will only 
                trigger reactive execution if the corresponding getter is 
                assigned to and referenced via a global variable.
                """
            ),
            "Tip: use state sparingly": (
                """
                You can get far using just `mo.ui`, without state. That said,
                judiciously using state can simplify the implementation of highly 
                interactive notebooks/apps, and also enables new use cases.
                """
            ),
        }
    )
    return


@app.cell
def __(get_counter, mo):
    mo.md(
        f"""
        Access the value of the state via its getter: `get_counter()` 
        returned **{get_counter()}**
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ### Setting State

        Set an element's state by calling its setter function.

        - Call it with a new value: `set_counter(1)`
        - Call it with a function that takes the current value and returns a new 
          one: `set_counter(lambda count: count + 1)`

        **State updates are reactive.** When you call a state's setter in one
        cell, _all other cells that reference the state getter via a global 
        variable_ are automatically
        run with the new state value. This is similar to how interacting with
        a UI element automatically runs all cells that use the element.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        **The `on_change` callback.** Every UI element takes an optional 
        `on_change` callback, a function
        that takes the new value of the element and does anything with it. You can
        use the setter function in an `on_change` callback to mutate state.

        **🌊 Try it!** Click the button below and watch what happens.
        """
    )
    return


@app.cell
def __(mo, set_counter):
    increment = mo.ui.button(
        label="increment",
        on_change=lambda _: set_counter(lambda v: v + 1),
    )

    decrement = mo.ui.button(
        label="decrement",
        on_change=lambda _: set_counter(lambda v: v - 1),
    )

    mo.hstack([increment, decrement], justify="center")
    return decrement, increment


@app.cell
def __(get_counter, mo):
    mo.md(
        f"""
        The counter's current value is **{get_counter()}**!

        This cell runs automatically on button click, even though it 
        doesn't reference either button. 
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.accordion(
        {
            "Tip: no self-loops": (
                """
                Calling a state's setter in one cell won't ever cause that same
                cell to re-execute, even if it reads that state getter. This 
                prevents accidental infinite loops and makes some things, like
                tying elements, easier."
                """
            )
        }
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("### Tied elements")
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        Use state to tie two UI elements to the same value.
        """
    )
    return


@app.cell
def __(mo):
    get_shared_state, set_shared_state = mo.state(0)
    return get_shared_state, set_shared_state


@app.cell
def __(get_shared_state, mo, set_shared_state):
    x = mo.ui.slider(
        0,
        10,
        value=get_shared_state(),
        on_change=set_shared_state,
        label="$x$:",
    )
    return x,


@app.cell
def __(get_shared_state, mo, set_shared_state):
    x_plus_one = mo.ui.number(
        1,
        11,
        value=get_shared_state() + 1,
        on_change=lambda v: set_shared_state(v - 1),
        label="$x + 1$:",
    )
    return x_plus_one,


@app.cell
def __(x, x_plus_one):
    [x, x_plus_one]
    return


@app.cell(hide_code=True)
def __(mo):
    mo.accordion(
        {
            "Tip: tying elements and cycles": (
                """
                To tie elements, you must `mo.state`, and the tied elements
                must be created in different cells (since self-loops with state
                are not allowed).
                """
            )
        }
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ### Example: Task list
        """
    )
    return


@app.cell
def __(dataclass, mo):
    @dataclass
    class Task:
        name: str
        done: bool = False

    get_tasks, set_tasks = mo.state([])
    task_list_mutated, set_task_list_mutated = mo.state(False)
    return (
        Task,
        get_tasks,
        set_task_list_mutated,
        set_tasks,
        task_list_mutated,
    )


@app.cell
def __(mo, task_list_mutated):
    task_list_mutated

    task_entry_box = mo.ui.text(placeholder="a task ...")
    return task_entry_box,


@app.cell
def __(Task, mo, set_task_list_mutated, set_tasks, task_entry_box):
    def add_task():
        if task_entry_box.value:
            set_tasks(lambda v: v + [Task(task_entry_box.value)])
            set_task_list_mutated(True)

    def clear_tasks():
        set_tasks(lambda v: [task for task in v if not task.done])
        set_task_list_mutated(True)

    add_task_button = mo.ui.button(
        label="add task",
        on_change=lambda _: add_task(),
    )

    clear_tasks_button = mo.ui.button(
        label="clear completed tasks", on_change=lambda _: clear_tasks()
    )
    return add_task, add_task_button, clear_tasks, clear_tasks_button


@app.cell
def __(Task, get_tasks, mo, set_tasks):
    task_list = mo.ui.array(
        [
            mo.ui.checkbox(value=task.done, label=task.name)
            for task in get_tasks()
        ],
        label="tasks",
        on_change=lambda v: set_tasks(
            lambda tasks: [
                Task(task.name, done=v[i]) for i, task in enumerate(tasks)
            ]
        ),
    )
    return task_list,


@app.cell
def __(add_task_button, clear_tasks_button, mo, task_entry_box):
    mo.hstack(
        [task_entry_box, add_task_button, clear_tasks_button], justify="start"
    )
    return


@app.cell
def __(mo, task_list):
    mo.as_html(task_list) if task_list.value else mo.md("No tasks! 🎉")
    return


@app.cell(hide_code=True)
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
    )
    return composite_elements,


@app.cell
def __(mo):
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
    return basic_ui_elements,


@app.cell
def __(mo):
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
    return construct_element,


@app.cell
def __(mo):
    def show_element(element):
        if element is not None:
            return mo.hstack([element], justify="center")
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
                {
                    f"Documentation on `mo.ui.{element.__name__}`": mo.doc(
                        element
                    )
                }
            )
    return documentation,


@app.cell
def __():
    from dataclasses import dataclass
    return dataclass,


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
