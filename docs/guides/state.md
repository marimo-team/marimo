# Reactive state

!!! warning "Stop! Read the interactivity guide first!"
    **Read the guide on [creating interactive
    elements](../guides/interactivity.md)** before reading this one!

!!! warning "Advanced topic!"
    This guide covers reactive state (`mo.state`), an advanced topic.

    **You likely don't need `mo.state`**. UI elements already have built-in
    state, their associated value, which you can access with their `value` attribute.
    For example, `mo.ui.slider()` has a value that is its current position on an
    interval, while `mo.ui.button()` has a value that can be configured to
    count the number of times it has been clicked, or to toggle between `True` and
    `False`. Additionally, interacting with UI elements bound to global variables
    [automatically executes cells](../guides/interactivity.md) that reference those
    variables, letting you react to changes by just reading their
    `value` attributes. **This functional paradigm is the preferred way of
    reacting to UI interactions in marimo.** **Chances are, the reactive
    execution built into UI elements will suffice.** (For example, [you don't need
    reactive state to handle a button click](../recipes.md#working-with-buttons).)

    That said, here are some signs you might need `mo.state`:

    - you need to maintain historical state related to a UI element that can't
      be computed from its built-in `value` (_e.g._, all values the user has
      ever input into a form)
    - you need to synchronize two different UI elements (_e.g._, so that
      interacting with either one controls the other)
    - you need to introduce cycles across cells

    **In over 99% of cases, you don't need and shouldn't use `mo.state`.** This
    feature can introduce hard-to-find bugs.

You can build powerful, interactive notebooks and apps using just `mo.ui` and
reactivity.

But sometimes, you might want interactions to mutate state:

- You're building a checklist, and you want to maintain a list of action
  items, even as you add and remove some items.

<div align="center" style="margin-top:2rem; margin-bottom:2rem">
<figure>
<video autoplay muted loop playsinline width="100%" height="100%" align="center">
    <source src="/_static/docs-state-task-list.mp4" type="video/mp4">
    <source src="/_static/docs-state-task-list.webm" type="video/webm">
</video>
</figure>
<figcaption>A proof-of-concept TODO list made using state.</figcaption>
</div>

- You want to tie two different UI elements so that updating **either** one
  updates the other.

<div align="center" style="margin-top:2rem; margin-bottom:2rem">
<figure>
<video autoplay muted loop playsinline width="100%" height="100%" align="center" src="/_static/docs-state-tied.webm">
</video>
<figcaption>Use state to tie two elements together in a cycle.</figcaption>
</figure>
</div>

!!! warning "Use reactive execution for uni-directional flow"
    If you just want the value of a single element to update another element,
    then **you shouldn't use `mo.state`**. Instead, use marimo's built-in
    reactive execution --- see the [interactivity guide](../guides/interactivity.md).

For cases like these, marimo provides the function [`mo.state()`](../api/state.md),
which creates a state object and returns a getter and setter function. When you
call the setter function in one cell, all other cells that reference the getter
function **via a global variable** are automatically run (similar to UI
elements).

!!! note "State and UI elements are similar"
    State is analogous to UI elements. When you interact
    with a UI element, all cells that reference that element via a global variable
    run automatically with the new value. In the same way, when you update state
    via the setter, all other cells that reference the getter via
    a global variable run automatically with the new value.

[`mo.state()`](../api/state.md) takes an initial state value as its argument, creates
a state object, and returns

- a getter function for reading the state
- a setter function for updating the state

For exaxmple,

```python
get_counter, set_counter = mo.state(0)
```

!!! attention "Assign state to global variables!"
    When using `mo.state()`, **you must assign the state getter to a global
    variable**. This is similar to UI elements work.

## Reading state

Access the state's latest value via the getter:

```python
get_counter()
```

## Updating state

You can update a state's value by calling its setter function with a new value.
For example,

```python
set_counter(1)
```

To update the state based on its current value, pass a function that takes
the current state value as an argument and returns a new value

```python
set_counter(lambda count: count + 1)
```

A single rule determines what happens next:

!!! tip "State reactivity rule"
    When a state setter function is called in one cell,  marimo
    automatically runs all _other_ cells that reference any **global** variables
    assigned to the state getter.

This rule has some important aspects:

1. Only cells that read the state getter via a global variable will be run.
2. The cell that called the setter won't be re-run, even if it references
   the getter. This restriction helps prevent against bugs that could
   otherwise arise. To lift this restriction, and allow the caller cell
   to be re-run, create your state with `mo.state(value, allow_self_loops=True)`.

Notice how similar this rule is to the reactivity rule for UI element
interactions.

## Using state with UI elements

Every UI element takes an optional `on_change` callback, a function that takes
the new value of the element and does anything with it. You can use the setter
function in an `on_change` callback to mutate state.

!!! note "Use state sparingly"
    You can get far using just `mo.ui`, without state, because marimo
    automatically runs cells that reference UI elements on interaction
    (see the [interactivity guide](../guides/interactivity.md)). Only
    use `on_change` callbacks as a last resort!

### Example: counter

The next few cells implement a counter controlled by two buttons. This
particular example could be implemented without state (try it!), but the
implementation using state is simpler.

<div align="center">
<figure>
<video autoplay muted loop playsinline width="100%" height="100%" align="center" src="/_static/docs-state-counter.webm">
</video>
</figure>
</div>

```python
import marimo as mo
```

```python
get_counter, set_counter = mo.state(0)

increment = mo.ui.button(
    label="increment",
    on_change=lambda _: set_counter(lambda v: v + 1),
)

decrement = mo.ui.button(
    label="decrement",
    on_change=lambda _: set_counter(lambda v: v - 1),
)

mo.hstack([increment, decrement], justify="center")
```

```python
mo.md(
    f"""
    The counter's current value is **{get_counter()}**!

    This cell runs automatically on button click, even though it
    doesn't reference either button.
    """
)
```

### Example: tied elements

This example shows how to tie two different UI elements so that each one's
value depends on the other. This is impossible to do without `mo.state`.

<div align="center">
<figure>
<video autoplay muted loop playsinline width="100%" height="100%" align="center" src="/_static/docs-state-tied.webm">
</video>
</figure>
</div>

```python
import marimo as mo
```

```python
get_x, set_x = mo.state(0)
```

```python
x = mo.ui.slider(
    0, 10, value=get_x(), on_change=set_x, label="$x$:"
)
```

```python
x_plus_one = mo.ui.number(
    1,
    11,
    value=get_x() + 1,
    on_change=lambda v: set_x(v - 1),
    label="$x + 1$:",
)
```

```python
[x, x_plus_one]
```

!!! note "Create tied UI elements in separate cells"
    Notice that we created the slider and number elements in different cells.
    When tying elements, this is necessary, because calling a setter
    in a cell queues all _other_ cells reading the state to run, not including
    the one that just called the setter.

!!! warning "Cycles at runtime"
    You can use state to introduce cycles across cells at runtime. This lets
    you tie multiple UI elements together, for example. Just be careful not to
    introduce an infinite loop!

    marimo programs are statically parsed into directed acyclic graphs (DAGs)
    involving cells, and state doesn't change that. Think of state setters
    as hooking into the DAG: at runtime, when they're invoked (and only when
    they're invoked), they trigger additional computation.

### Example: todo list

The next few cells use state to create a todo list.

<div align="center">
<figure>
<video autoplay muted loop playsinline width="100%" height="100%" align="center" src="/_static/docs-state-task-list.webm">
</video>
</figure>
</div>

```python
import marimo as mo
from dataclasses import dataclass
```

```python
@dataclass
class Task:
    name: str
    done: bool = False


get_tasks, set_tasks = mo.state([])
task_added, set_task_added = mo.state(False)
```

```python
# Refresh the text box whenever a task is added
task_added

task_entry_box = mo.ui.text(placeholder="a task ...")
```

```python
def add_task():
    if task_entry_box.value:
        set_tasks(lambda v: v + [Task(task_entry_box.value)])
        set_task_added(True)

def clear_tasks():
    set_tasks(lambda v: [task for task in v if not task.done])

add_task_button = mo.ui.button(
    label="add task",
    on_change=lambda _: add_task(),
)

clear_tasks_button = mo.ui.button(
    label="clear completed tasks",
    on_change=lambda _: clear_tasks()
)
```

```python
task_list = mo.ui.array(
    [mo.ui.checkbox(value=task.done, label=task.name) for task in get_tasks()],
    label="tasks",
    on_change=lambda v: set_tasks(
        lambda tasks: [Task(task.name, done=v[i]) for i, task in enumerate(tasks)]
    ),
)
```

```python
mo.hstack(
    [task_entry_box, add_task_button, clear_tasks_button], justify="start"
)
```
