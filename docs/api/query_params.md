# Query Parameters

Use `mo.query_params` to access query parameters passed to the notebook. You
can also use `mo.query_params` to set query parameters in order to keep track
of state in the URL. This is useful for bookmarking or sharing a particular
state of the notebook while running as an application with `marimo run`.

```{eval-rst}
.. autofunction:: marimo.query_params
```

```{admonition} CLI arguments
:class: note

You can also access command-line arguments passed to the notebook using
`mo.cli_args`. This allows you to pass arguments to the notebook that are not controllable by the user.
```
