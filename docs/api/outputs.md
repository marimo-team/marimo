# Outputs

## Cell outputs

!!! note "Cell outputs"
Every cell in a marimo notebook can have a visual **output**. When editing,
outputs are displayed above cells. When running a notebook as an app,
its UI is an arrangement of outputs.

    A cell's output is by default its last expression. You can also create outputs
    programmatically, using `mo.output.replace()` and `mo.output.append()`.

::: marimo.output.replace
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
::: marimo.redirect_stdout

::: marimo.redirect_stderr
::: marimo.capture_stdout

::: marimo.capture_stderr
