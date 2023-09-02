# State

```{admonition} Advanced topic!
:class: warning

This guide covers reactive state, an advanced topic. Unless you're
making complex apps, you likely won't need the concepts in this guide. You
most likely don't need state for your day-to-day exploratory data analysis
or for running numerical experiments.

With that in mind, we recommend skipping this guide and only returning here if
you feel limited in your options to responding to user interactions.
```

You can build powerful, interactive notebooks and apps using just `mo.ui` and
reactivity.

Sometimes, however, you might want interactions to mutate state:

- Maybe you're building a checklist, and you want to maintain a list of action
  items, even as you add and remove some items.

<div align="center" style="margin-top:2rem; margin-bottom:2rem">
<figure>
<img src="/_static/docs-state-task-list.gif"/>
</figure>
<figcaption>A proof-of-concept TODO list made using state.</figcaption>
</div>


- Maybe you want to tie two different UI elements, so that updating one updates
  the other.

<div align="center" style="margin-top:2rem; margin-bottom:2rem">
<figure>
<img src="/_static/docs-state-tied.gif"/>
<figcaption>Use state to tie two elements together.</figcaption>
</figure>
</div>


For cases like these, marimo provides the function [`mo.state`](/api/state),
which returns a state object and a function that updates the state. When you
call the setter function in one cell, all other cells that reference the state
object **via a global variable** are automatically run (similar to UI elements).


```{admonition} State and UI Elements
:class: tip

In marimo, a `State` object is analogous to a UI element. When you interact
with a UI element, all cells that reference that element via a global variable
run automatically with the new value. In the same way, when you update a state
object via its setter, all other cells that reference the object via
a global variable run automatically with the new value.

`State` is particularly useful when used in conjunction with a `UIElement`'s
`on_change` callback to run side effects based on user input. You can also use
it to introduce cycles into a marimo program. Just be careful not to introduce
an infinite loop!
```

## Creating state

[`mo.state`](/api/state) takes an initial state value as its argument, and
returns

- a `State` object;
- a function you can call to update the state value.

For exaxmple,

```python
counter, set_counter = mo.state(0)
```

```{admonition} Assign state to global variables!
:class: attention

When using `mo.state()`, **you must assign the `State` object
to a global variable**. This is similar to UI elements work.
```

## Reading state

Access the state's latest value via the `value` attribute:

```python
counter.value
```

## Updating state

You can update a state's value by calling its setter function with a new value.
For example,

```python
set_counter(1)
```

or

```python
set_counter(counter.value + 1)
```

A single rule determines what happens next:

```{admonition} State reactivity rule
:class: tip

When the setter function for a `State` object is run in one cell, marimo
automatically runs all _other_ cells that reference any **global** variables
assigned to the state object.
```

<div align="center">
<figure>
<img src="/_static/docs-state-update.gif"/>
</figure>
</div>

This rule has some important aspects:

1. The cell that called the setter won't be re-run, even if it reads
   the `State` object's value.
2. Only cells that read the state via a global variable will be run.

Notice how similar this rule is to the reactivity rule for UI elements.


## Using state with UI Elements

Every UI element takes an optional `on_change` callback, a function that takes
the new value of the element and does anything with it. You can use the setter
function in an `on_change` callback to mutate state.

```{admonition} Use state sparingly
:class: tip

You can get far using just `mo.ui`, without state. But judiciously using
state can simplify the implementation of highly interactive notebooks/apps, and
also enables new use cases. The next few examples showcase good uses of state.
```

### Example: counter
The next few cells implement a counter controlled by two buttons. This
particular example could be implemented without state (try it!), but the
implementation using state is simpler. 


<div align="center">
<figure>
<img src="/_static/docs-state-counter.gif"/>
</figure>
</div>


```python
import marimo as mo
```

```python
counter, set_counter = mo.state(0)

increment = mo.ui.button(
    label="increment",
    on_change=lambda _: set_counter(counter.value + 1),
)

decrement = mo.ui.button(
    label="decrement",
    on_change=lambda _: set_counter(counter.value - 1),
)

mo.hstack([increment, decrement], justify="center")
```

```python
mo.md(
    f"""
    The counter's current value is **{counter.value}**!

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
<img src="/_static/docs-state-tied.gif"/>
</figure>
</div>


```python
import marimo as mo
```

```python
shared_state, set_shared_state = mo.state(0)
```

```python
x = mo.ui.slider(
    0, 10, value=shared_state.value, on_change=set_shared_state, label="$x$:"
)
```

```python
x_plus_one = mo.ui.number(
    1,
    11,
    value=shared_state.value + 1,
    on_change=lambda v: set_shared_state(v - 1),
    label="$x + 1$:",
)
```

```python
[x, x_plus_one]
```

```{admonition} Create tied UI elements in separate cells
:class: tip

Notice that we created the slider and number elements in different cells.
When tying elements, this is necessary, because calling a setter
in a cell queues all _other_ cells reading the state to run, not including
the one that just called the setter.
```

### Example: todo list

The next few cells use state to create a todo list.

<div align="center">
<figure>
<img src="/_static/docs-state-task-list.gif"/>
</figure>
</div>


```python
import marimo as mo
```

```python
@dataclass
class Task:
    name: str
    done: bool = False


tasks, set_tasks = mo.state([])
task_list_mutated, set_task_list_mutated = mo.state(False)
```

```python
# Refresh the text box whenever the task list is mutated
task_list_mutated

task_entry_box = mo.ui.text(placeholder="a task ...")
```

```python
def add_task():
    if task_entry_box.value:
        set_tasks(tasks.value + [Task(task_entry_box.value)])
        set_task_list_mutated(True)

def clear_tasks():
    set_tasks(
        [task for task in tasks.value if not task.done]
    )
    set_task_list_mutated(True)

add_task_button = mo.ui.button(
    label="add task",
    on_change=lambda _: add_task(),
)

clear_tasks_button = mo.ui.button(
    label="clear completed tasks",
    on_change=lambda _: clear_tasks()
)
```

```
task_list = mo.ui.array(
    [mo.ui.checkbox(value=task.done, label=task.name) for task in tasks.value],
    label="tasks",
    on_change=lambda v: set_tasks(
        [Task(task.name, done=v[i]) for i, task in enumerate(tasks.value)]
    ),
)
```

```
mo.hstack(
    [task_entry_box, add_task_button, clear_tasks_button], justify="start"
)
```
