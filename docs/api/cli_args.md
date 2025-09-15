# Command Line Arguments

When running as a script with `python notebook.py`, command-line arguments
are available to your program in `sys.argv`, just like any other Python
program. This means you can use
[`argparse`](https://docs.python.org/3/library/argparse.html),
[`simple-parsing`](https://github.com/lebrice/SimpleParsing), and other tools
for specifying and parsing arguments.

You can also use tools like `argparse` when running as a notebook (`marimo
edit` or `marimo run`) or exporting to HTML, IPYNB or another format (`marimo
export`). In these cases, `sys.argv` is set to the notebook filename followed by any args
following the `--` separator.

For example, for

```bash
marimo edit notebook.py -- --lr 1e-4 --epochs 15
```

sets `sys.argv` to `["notebook.py", "--lr", "1e-4", "--epochs", "15"]`.

## Programmatic execution with CLI arguments

When running a marimo app programmatically using `app.run()`, you can pass
CLI arguments directly to the method:

```python
import marimo

app = marimo.App()

@app.cell
def process_data():
    import marimo as mo
    args = mo.cli_args()
    batch_size = args.get("batch_size", 32)
    return batch_size,

# Run with CLI arguments
outputs, defs = app.run(args=["--batch_size", "64", "--model", "transformer"])
```

If you call `app.run()` without any CLI arguments, the app will inherit the
CLI arguments from the parent process (i.e., from `sys.argv`).

This is particularly useful for testing, batch processing, or when embedding
marimo apps in larger Python applications.

For usage examples, see the guide on [running as a script](../guides/scripts.md).

## Utility function for parsing arguments

marimo provides a utility function called `mo.cli_args()` for parsing arguments
from strings into primitive data types (`int`, `bool`, `float`, `str`).
However, unlike `argparse` and `simple-parsing`, this function does not let you
declare your program's arguments, nor does it generate help text. **For these
reasons, we recommend using `argparse` or `simple-parsing` instead.**

```bash
python notebook.py -- --arg1 value1 --arg2 value2
# mo.cli_args() == {'arg1': 'value1', 'arg2': 'value2'}

python notebook.py -- --arg1=10 --arg2=true --arg3
# mo.cli_args() == {'arg1': 10, 'arg2': True, 'arg3': ''}

python notebook.py -- --arg1 10.5 --arg2 hello --arg2 world
# mo.cli_args() == {'arg1': 10.5, 'arg2': ['hello', 'world']}
```

::: marimo.cli_args

!!! note "Query Parameters"
    You can also access query parameters passed to the notebook using
    `mo.query_params`. This allows you to pass arguments to the notebook that can be controlled by the user.
