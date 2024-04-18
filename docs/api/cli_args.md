# Command Line Arguments

Use `mo.cli_args` to access command-line arguments passed to the notebook. This allows you to pass arguments to the notebook that are not controllable by the user. The arguments will be parsed from the command line when running the notebook as an application with `marimo run` or `marimo edit`. These arguments are passed after the notebook name and are separated from the notebook arguments by a double dash `--`.

Some examples passing command-line arguments to the notebook:

```bash
marimo run app.py -- --arg1 value1 --arg2 value2
# {'arg1': 'value1', 'arg2': 'value2'}

marimo run app.py -- --arg1=10 --arg2=true --arg3
# {'arg1': 10, 'arg2': True, 'arg3': ''}

marimo run app.py -- --arg1 10.5 --arg2 hello --arg2 world
# {'arg1': 10.5, 'arg2': ['hello', 'world']}
```

```{eval-rst}
.. autofunction:: marimo.cli_args
```

```{admonition} Query Parameters
:class: note

You can also access query parameters passed to the notebook using
`mo.query_params`. This allows you to pass arguments to the notebook that can be controlled by the user.
```
