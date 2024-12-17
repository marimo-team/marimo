# Query Parameters

Use `mo.query_params` to access query parameters passed to the notebook. You
can also use `mo.query_params` to set query parameters in order to keep track
of state in the URL. This is useful for bookmarking or sharing a particular
state of the notebook while running as an application with `marimo run`.

::: marimo.query_params

!!! note "CLI arguments"

You can also access command-line arguments passed to the notebook using
`mo.cli_args`. This allows you to pass arguments to the notebook that are not controllable by the user.
