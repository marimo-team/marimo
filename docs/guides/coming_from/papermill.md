# Coming from Papermill

If you're familiar with Papermill and looking to transition to marimo, this guide will help you understand how to achieve similar functionality using marimo's features.

## Parameterizing Notebooks

**Papermill**

Papermill allows you to parameterize notebooks by defining a "parameters" cell and injecting values at runtime.

**marimo**

marimo offers two main ways to parameterize notebooks:

1. **Command Line Arguments**:
   Use `mo.cli_args` to access command-line arguments passed to your notebook.

   ```python
   import marimo as mo

   # Access CLI args
   args = mo.cli_args
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
   params = mo.query_params
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

marimo notebooks are pure Python files, making them easy to execute programmatically:

1. **As a module**:

   ```python
   import notebook

   notebook.app.run()
   ```

2. **Using subprocess**:

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
   marimo export html notebook.py -o notebook.html
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
