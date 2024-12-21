# Best practices

Here are best practices for writing marimo notebooks.

**Use global variables sparingly.** Keep the number of global variables in your
program small to avoid name collisions. If you have intermediate variables,
encapsulate them in functions or prefix them with an underscore (`_tmp = ...`) to
make them local to a cell.

**Use descriptive names.** Use descriptive variable names, especially for
global variables. This will help you minimize name clashes, and will also
result in better code.

**Use functions.** Encapsulate logic into functions to avoid polluting the
global namespace with
temporary or intermediate variables, and to avoid code duplication.

**Use [`mo.stop`][marimo.stop] to stop execution.** Use [`mo.stop`][marimo.stop]
to stop a cell from running when a condition is true; this is helpful
when working with expensive notebooks. For example, prevent a cell from running
until a button is clicked using [`mo.ui.run_button`][marimo.ui.run_button] and
[`mo.stop`][marimo.stop].

!!! caution "Expensive notebooks"
    For more tips on working with expensive notebooks, see the
    associated [guide](../guides/expensive_notebooks.md).

**Use Python modules.** If your notebook gets too long, split complex logic
into helper Python modules and import them into your notebook. Use marimo's
built-in [module
reloading](../guides/configuration/runtime_configuration.md#on-module-change)
to automatically bring changes from your modules into your notebook.

**Minimize mutations.** marimo does not track mutations to objects. Try to
only mutate an object in the cell that creates it, or create new objects
instead of mutating existing ones.

??? example "Example"

    _Don't_ split up declarations and mutations over multiple cells. For example, _don't
    do this:_

    ```python
    l = [1, 2, 3]
    ```

    ```python
    l.append(new_item())
    ```

    Instead, _do_ **declare and mutate in the same cell**:

    ```python
    l = [1, 2, 3]
    ...
    l.append(new_item())
    ```

    or, if working in multiple cells, **declare a new variable based on the old
    one**:

    ```python
    l = [1, 2, 3]
    ```

    ```python
    extended_list = l + [new_item()]
    ```
**Don't use state and `on_change` handlers.** Don't use `on_change` handlers
to react to UI interactions. Instead, use marimo's built-in [reactive execution
for interactive elements](../guides/interactivity.md).

**Write idempotent cells.**
Write cells whose outputs and behavior are the same
when given the same inputs (references); such cells are called idempotent. This
will help you avoid bugs and cache expensive intermediate computations.
