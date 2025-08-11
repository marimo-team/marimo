# Running cells

marimo _reacts_ to your code changes: run a cell, and all other cells that
refer to the variables it defines are automatically run with the latest data.
This keeps your code and outputs consistent, and eliminates bugs before they
happen.

??? question "Why run cells reactively?"
    marimo's "reactive" execution model makes your notebooks more reproducible
    by eliminating hidden state and providing a deterministic execution order.
    It also powers marimo's support for [interactive
    elements](../guides/interactivity.md), for running as apps, and executing as
    scripts.

    How marimo runs cells is one of the biggest differences between marimo and
    traditional notebooks like Jupyter. Learn more at our
    [FAQ](../faq.md#faq-jupyter).

!!! tip "Working with expensive notebooks"
    marimo provides tools for working with expensive notebooks, in which cells
    might take a long time to run or have side-effects.

    *  The [runtime can be configured](configuration/runtime_configuration.md)
       to be **lazy** instead of
       automatic, marking cells as stale instead of running them.
    *  Use [`mo.stop`][marimo.stop] to conditionally
       stop execution at runtime.

    See [the expensive notebooks guide](expensive_notebooks.md) for more tips.

## How marimo runs cells

marimo statically analyzes each cell (i.e., without running it) to determine
its

- references, the global variables it reads but doesn't define;
- definitions, the global variables it defines.

It then forms a directed acyclic graph (DAG) on cells, with an edge from
one cell to another if the latter references any of the definitions of the
former. When a cell is run, its descendants are marked for execution.

!!! tip "Visualizing the DAG"
    marimo provides several tools to help you visualize and navigate this dependency graph,
    including a [dependency explorer](editor_features/dataflow.md#dependency-explorer), 
    [minimap](editor_features/dataflow.md#minimap),
    and [reactive reference highlighting](editor_features/dataflow.md#reactive-reference-highlighting).
    
    See the [understanding dataflow](editor_features/dataflow.md) guide for details.

!!! important "Runtime Rule"
    When a cell is run, marimo automatically runs all other cells that
    **reference** any of the global variables it **defines**.

marimo [does not track mutations](#variable-mutations-are-not-tracked) to
variables, nor assignments to attributes. That means that if you assign an
attribute like `foo.bar = 10`, other cells referencing `foo.bar` will _not_ be
run.

### Execution order

The order cells are executed in is determined by the relationships between
cells and their variables, not by the order of cells on the page (similar
to a spreadsheet). This lets you organize your code in whatever way makes the
most sense to you. For example, you can put helper functions at the bottom of
your notebook.

### Deleting a cell deletes its variables

In marimo, _deleting a cell deletes its global variables from program memory_.
Cells that previously referenced these variables are automatically re-run and
invalidated (or marked as stale, depending on your [runtime
configuration](configuration/runtime_configuration.md)). In this way, marimo
eliminates a common cause of bugs in traditional notebooks like Jupyter.

<!-- <div align="center">
<figure>
<video autoplay muted loop playsinline width="100%" height="100%" align="center" src="/_static/docs-delete-cell.webm">
</video>
<figcaption>No hidden state: deleting a cell deletes its variables.</figcaption>
</figure>
</div> -->

<a name="reactivity-mutations"></a>

### Variable mutations are not tracked

marimo does not track mutations to objects, _e.g._, mutations like
`my_list.append(42)` or `my_object.value = 42` don't trigger reactive re-runs of
other cells. **Avoid defining a variable in one cell and
mutating it in another**.

??? note "Why not track mutations?"

    Tracking mutations reliably is impossible in Python. Reacting to mutations
    could result in surprising re-runs of notebook cells.

If you need to mutate a variable (such as adding a new column to a dataframe),
you should perform the mutation in the same cell as the one that defines it,
or try creating a new variable instead.

??? example "Create new variables, don't mutate existing ones"

    === "Do this ..."

        ```python
        l = [1]
        ```

        ```python
        extended_list = l + [2]
        ```

    === "... not this"

        ```python
        l = [1]
        ```

        ```python
        l.append(2)
        ```

??? example "Mutate variables in the cells that define them"

    === "Do this ..."

        ```python
        df = pd.DataFrame({"my_column": [1, 2]})
        df["another_column"] = [3, 4]
        ```


    === "... not this"

        ```python
        df = pd.DataFrame({"my_column": [1, 2]})
        ```

        ```python
        df["another_column"] = [3, 4]
        ```

## Global variable names must be unique

**marimo requires that every global variable be defined by only one cell.**
This lets marimo keep code and outputs consistent.

!!! tip "Global variables"
    A variable can refer to any Python object. Functions, classes, and imported
    names are all variables.

This rule encourages you to keep the number of global variables in your
program small, which is generally considered good practice.

### Creating temporary variables

marimo provides two ways to define temporary variables, which can
help keep the number of global variables in your notebook small.

#### Creating local variables

Variables prefixed with an underscore (_e.g._, `_x`) are "local" to a
cell: they can't be read by other cells. Multiple cells can reuse the same
local variables names.

#### Encapsulating code in functions

If you want most or all the variables in a cell to be temporary, prefixing each
variable with an underscore to make it local may feel inconvenient. In these
situations we recommend encapsulating the temporary variables in a function.

For example, if you find yourself copy-pasting the same plotting code across
multiple cells and only tweaking a few parameters, try the following pattern:

```python
def _():
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot([1, 2])
    return ax

_()
```

Here, the variables `plt`, `fig`, and `ax` aren't added to the globals.

### Managing memory

Because variable names must be unique, you cannot reassign variables as a means
of freeing memory. Instead, manage memory by encapsulating code in functions or
using the `del` operator. See our guide on [expensive
notebooks](expensive_notebooks.md#manage-memory) to learn more.

## Configuring how marimo runs cells

Through the notebook settings menu, you can configure how and when marimo runs
cells. In particular, you can disable autorun on startup, disable autorun
on cell execution, and enable a module autoreloader. Read our
[runtime configuration guide](configuration/runtime_configuration.md) to learn more.

## Disabling cells

Sometimes, you may want to edit one part of a notebook without triggering
automatic execution of its dependent cells. For example, the dependent cells
may take a long time to execute, and you only want to iterate on the first part
of a multi-cell computation.

For cases like this, marimo lets you **disable** cells: when a cell is
disabled, it and its dependents are blocked from running.

<div align="center">
<figure>
<video autoplay muted loop playsinline width="100%" height="100%" align="center" src="/_static/docs-disable-cell.webm">
</video>
<figcaption>Disabling a cell blocks it from running.</figcaption>
</figure>
</div>

When you re-enable a cell, if any of the cell's ancestors ran while it was
disabled, marimo will automatically run it.

<div align="center">
<figure>
<video autoplay muted loop playsinline width="100%" height="100%" align="center" src="/_static/docs-enable-cell.webm">
</video>
<figcaption>Enable a cell through the context menu. Stale cells run
automatically.</figcaption>
</figure>
</div>
