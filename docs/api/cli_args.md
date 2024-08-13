# Command Line Arguments

Use `mo.cli_args` to access command-line arguments passed to the notebook. This
allows you to pass arguments to the notebook that are not controllable by the
user. The arguments will be parsed from the command line when running the
notebook as an application with `marimo run` or `marimo edit`; they will also
be parsed from the command line when running as a script.

Some examples passing command-line arguments to the notebook when running
as a script:

```bash
python notebook.py -- --arg1 value1 --arg2 value2
# mo.cli_args() == {'arg1': 'value1', 'arg2': 'value2'}

python notebook.py -- --arg1=10 --arg2=true --arg3
# mo.cli_args() == {'arg1': 10, 'arg2': True, 'arg3': ''}

python notebook.py -- --arg1 10.5 --arg2 hello --arg2 world
# mo.cli_args() == {'arg1': 10.5, 'arg2': ['hello', 'world']}
```

In each example, `python` can be replaced as `marimo run` (for running as
an app) or `marimo edit` (for running as a notebook).

```{eval-rst}
.. autofunction:: marimo.cli_args
```

```{admonition} Query Parameters
:class: note

You can also access query parameters passed to the notebook using
`mo.query_params`. This allows you to pass arguments to the notebook that can be controlled by the user.
```
