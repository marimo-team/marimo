# Coming from Papermill

marimo provides built-in support for parametrizing and executing marimo
notebooks. If you're familiar with Papermill, this guide will help you
understand how to achieve similar functionality using marimo's features.

## Parameterizing Notebooks

**Papermill**

Papermill allows you to parameterize Jupyter notebooks by defining a "parameters" cell
and injecting values at runtime.

**marimo**

marimo offers two main ways to parameterize notebooks:

1. **Command Line Arguments**:
   Use [`mo.cli_args`](../../api/cli_args.md) to access command-line arguments passed to your notebook.

   ```python
   import marimo as mo

   # Access CLI args
   args = mo.cli_args()
   param1 = args.get("param1", "default_value")
   ```

   Run your notebook as a script with:

   ```bash
   python notebook.py -- --param1 value1
   ```

   Run your notebook as an app with:

   ```bash
   marimo run notebook.py -- --param1 value1
   ```

2. **Query Parameters**:
   For web apps, use `mo.query_params` to access URL query parameters.

   ```python
   import marimo as mo

   # Access query params
   params = mo.query_params()
   param1 = params.get("param1", "default_value")
   ```

   Access your app with:

   ```bash
   marimo run notebook.py
   ```

   Then visit:

   ```bash
   http://your-app-url/?param1=value1
   ```

## Executing Notebooks

**Papermill**

Papermill allows you to execute notebooks programmatically and pass parameters.

**marimo**

marimo notebooks are pure Python files, making them easy to execute
programmatically.

1. **Running a named cell**:

   After naming a cell in your file, you can run it using the
   [cell execution API][marimo.Cell.run].

   ```python
   from my_notebook import my_cell

   # last_expression is the visual output of the cell
   # definitions is a dictionary of the variables defined by the cell
   last_expression, definitions = my_cell.run()
   ```

   This API also allows for parametrizing the inputs to the cell; to learn more,
   make sure to checkout [the example][marimo.Cell.run] in our API reference.

2. **Programmatic execution with CLI arguments**:

   You can run a marimo app directly with CLI arguments:

   ```python
   import marimo
   from my_notebook import app

   # Run the app with CLI arguments
   outputs, defs = app.run("--param1", "value1", "--param2", "value2")
   ```

3. **Using subprocess**:

   ```python
   import subprocess

   subprocess.run(["python", "notebook.py", "--", "--param1", "value1"])
   ```

## Storing or Sharing Artifacts

**Papermill**

Papermill can store executed notebooks with output.

**marimo**

marimo offers several options for storing and sharing outputs:

1. **Export to HTML**:

   ```bash
   marimo export html notebook.py -o notebook.html -- -arg1 foo --arg2 bar
   ```

2. **Deploy as Web App**:

   ```bash
   marimo run notebook.py
   ```

3. **Auto-export HTML**:
   You can configure marimo to automatically export to HTML during the editing process.
   This is configured in the marimo application settings directly in the editor.
   This way, after changes are made to your notebook, an HTML snapshot is generated,
   and placed in a `.marimo/` directory in the same location as your notebook.

## Workflow Integration

**Papermill**

Papermill is often used in data pipelines and workflow systems.

**marimo**

marimo notebooks can be easily integrated into workflows:

1. **As Python Scripts**:
   marimo notebooks are Python files, so they can be executed directly in most workflow systems.
   See [our examples](https://github.com/marimo-team/marimo/tree/main/examples) for integrating with
   popular tools.

2. **Programmatic Execution**:
   Importing notebook as Python modules or executing via subprocess allows for chaining together multiple notebooks in a workflow.
