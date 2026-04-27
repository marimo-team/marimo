# Run as a script

You can run marimo notebooks as scripts at the command line, just like
any other Python script. For example,

```bash
python my_marimo_notebook.py
```

Running a notebook as a script is useful when your notebook has side-effects,
like writing to disk. Print statements and other console outputs will show
up in your terminal.

marimo notebooks can also [double as importable
modules](https://docs.marimo.io/guides/reusing_functions/), providing libraries
of functions and classes that you can reuse in other programs:

```python
from my_notebook import my_function
```

Read our guide on [reusable functions](reusing_functions.md) for details.


!!! tip "Check before running"

    Before running a notebook as a script, you can use marimo's linter to check for issues that might prevent execution:

    ```bash
    marimo check my_marimo_notebook.py
    ```

    See the [Lint Rules](lint_rules/index.md) guide for more information about marimo's linting system.


!!! note "Saving notebook outputs"

    To run as a script while also saving HTML of the notebook outputs, use

    ```bash
    marimo export html notebook.py -o notebook.html
    ```

    You can also pass command-line arguments to your notebook during export.
    Separate these args from the command with two dashes:

    ```bash
    marimo export html notebook.py -o notebook.html -- -arg value
    ```

    Exporting to other formats, such as ipynb, is also possible:

    ```bash
    marimo export ipynb notebook.py -o notebook.ipynb -- -arg value
    ```

## Command-line arguments

When run as a script, you can access your notebook's command-line arguments
through `sys.argv`, just like any other Python program. This also
means you can declare your notebook's command-line arguments using Python
libraries like [`argparse`](https://docs.python.org/3/library/argparse.html)
and [`simple-parsing`](https://github.com/lebrice/SimpleParsing).

These examples shows how to conditionally assign values to variables based on
command-line arguments when running as a script, and use default values when
running as a notebook.

### argparse

/// marimo-embed-file
    filepath: examples/running_as_a_script/sharing_arguments.py
///

### simple-parsing

/// marimo-embed-file
    filepath: examples/running_as_a_script/with_simple_parsing.py
///


## Example: scheduled execution

marimo notebooks are Python files, so any scheduler that runs Python scripts
can run marimo notebooks. This includes
[cron](https://en.wikipedia.org/wiki/Cron),
[Airflow](https://airflow.apache.org/), [Prefect](https://www.prefect.io/),
and other tools. You can pass variables from the command line and [reuse
functions](reusing_functions.md) from notebooks in other jobs as well.

### GitHub Action

Run notebooks on a schedule with [GitHub Actions](https://docs.github.com/en/actions/reference/events-that-trigger-workflows#schedule). This example assumes [inline dependencies](package_management/inlining_dependencies.md):

```yaml
name: Run marimo notebook daily

on:
  schedule:
    - cron: '0 9 * * *'

jobs:
  run-marimo:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.12'
    - uses: astral-sh/setup-uv@v7
    - run: uv run path/to/notebook.py
```
