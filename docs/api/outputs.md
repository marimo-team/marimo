# Outputs

## Cell outputs

```{admonition} Cell outputs
:class: note

Every cell in a marimo notebook can have a visual **output**. When editing,
outputs are displayed above cells. When running a notebook as an app,
its UI is an arrangement of outputs.

A cell's output is by default its last expression. You can also create outputs
programmatically, using `mo.output.replace()` and `mo.output.append()`.
```

```{eval-rst}
.. autofunction:: marimo.output.replace
```

```{eval-rst}
.. autofunction:: marimo.output.append
```

```{eval-rst}
.. autofunction:: marimo.output.clear
```

```{admonition} Last expression replaces existing output
:class: warning

Ending a cell with a non-`None` expression is the same as calling
`mo.output.replace()` on it: the last expression replaces any output you may have
already written. Wrap the last expression in `mo.output.append` if you want
to add to an existing output instead of replacing it.
```

## Console outputs

```{admonition} Console outputs
:class: note

Text written to `stdout`/`stderr`, including print statements
and logs, shows up in a console output area below a cell.

By default, these console outputs don't appear when running a marimo notebook
as an app. If you do want them to appear in apps, marimo provides utility
functions for capturing console outputs and redirecting them to cell outputs.
```

```{eval-rst}
.. autofunction:: marimo.redirect_stdout
```

```{eval-rst}
.. autofunction:: marimo.redirect_stderr
```

```{eval-rst}
.. autofunction:: marimo.capture_stdout
```

```{eval-rst}
.. autofunction:: marimo.capture_stderr
```
