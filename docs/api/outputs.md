# Outputs

## Cell outputs

!!! note "Cell outputs"
    Every cell in a marimo notebook can have a visual **output**. When editing,
    outputs are displayed above cells. When running a notebook as an app,
    its UI is an arrangement of outputs.

    A cell's output is by default its last expression. You can also create outputs
    programmatically, using `mo.output.replace()` and `mo.output.append()`.

::: marimo.output.replace

!!! tip "**Watch `mo.output.replace` in action**"
    See a demo of how `mo.output.replace` works in this [short YouTube video](https://youtube.com/shorts/tCMeQb-PqNU?si=7PeFzQJzNvXsLoXN).

::: marimo.output.append

::: marimo.output.clear
::: marimo.output.replace_at_index

!!! warning "Last expression replaces existing output"
    Ending a cell with a non-`None` expression is the same as calling
    `mo.output.replace()` on it: the last expression replaces any output you may have
    already written. Wrap the last expression in `mo.output.append` if you want
    to add to an existing output instead of replacing it.

### Display cell code in marimo's app views

Use `mo.show_code()` to display the cell's code in the output area, which
will then be visible in all app views.

::: marimo.show_code

## Console outputs

/// admonition | Console outputs
    type: note

Text written to `stdout`/`stderr`, including print statements
and logs, shows up in a console output area below a cell.

By default, these console outputs don't appear when running a marimo notebook
as an app. If you do want them to appear in apps, marimo provides utility
functions for capturing console outputs and redirecting them to cell outputs.
///

::: marimo.redirect_stdout

::: marimo.redirect_stderr
::: marimo.capture_stdout

::: marimo.capture_stderr
