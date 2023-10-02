# Console outputs

Outputs written to `stdout` or `stderr`, including print statements
and logs, show up in a console output area below a cell.

By default, these console outputs don't appear when running a marimo notebook
as an app. If you do want them to appear in apps, marimo provides utility
functions for capturing console outputs and redirecting them to cell outputs.

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
