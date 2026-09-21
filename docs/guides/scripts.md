# Run notebooks as scripts

You can run marimo notebooks as scripts at the command line, just like
any other Python script. For example,

```bash
python my_marimo_notebook.py
```

The `python` command uses your current environment, which must contain marimo and the
notebook's dependencies. Activate it first if you manage it yourself.

uv and Pixi can prepare the environment and run the script using its
[declared dependencies](#running-with-declared-dependencies).

Running a notebook as a script is useful when your notebook has side-effects,
like writing to disk. Print statements and other console outputs will show
up in your terminal.

You can also [import functions and classes](reusing_functions.md) from notebooks
into other Python programs.


## Running with declared dependencies

Use your package manager to run a notebook with its declared requirements.

### Running with inline dependencies

A [sandboxed notebook](package_management/sandboxes.md) declares
its requirements as inline script metadata (PEP 723). uv and Pixi can read that
metadata, prepare an environment, and run the notebook without opening the editor:

=== "uv"

    ```bash
    uv run notebook.py
    ```

=== "Pixi"

    ```bash
    pixi run --script notebook.py
    ```

Use Pixi for notebooks that require Conda dependencies declared under
`tool.pixi`. Running a notebook with `python` directly does not install its
inline requirements.

### Running in a project

For a notebook that uses [project dependencies](package_management/projects.md),
run it from the project directory:

=== "uv"

    ```bash
    uv run notebook.py
    ```

    If the notebook contains inline script metadata, uv uses that metadata
    instead of the project's dependencies.

=== "Pixi"

    ```bash
    pixi run python notebook.py
    ```

    `pixi run python` uses the workspace environment. Use `pixi run --script notebook.py`
    instead to prepare an environment from the notebook's inline requirements.

=== "Poetry"

    ```bash
    poetry run python notebook.py
    ```

See [package management](package_management/index.md) for choosing between
project dependencies and a notebook sandbox.

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

Run notebooks on a schedule with [GitHub Actions](https://docs.github.com/en/actions/reference/events-that-trigger-workflows#schedule). This example assumes [inline dependencies](package_management/sandboxes.md):

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
